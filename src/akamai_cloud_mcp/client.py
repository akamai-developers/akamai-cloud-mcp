"""LinodeClient wrapper: the single GET-only gateway to the Linode API.

Read-only is enforced structurally here. This module only ever issues GET. It
never calls a mutating SDK method (create/update/delete/save/invalidate) and
never uses an httpx verb other than GET. The static read-only scan in the test
suite asserts this stays true.

The official `linode_api4` SDK is SYNCHRONOUS (requests-style). We reuse its
auth, retry, and pagination through `client.get(path)` for the escape hatch and
for endpoints the SDK does not model. `httpx` is only a last-resort fallback.

A small in-process cache holds the public price/type endpoints for ~24h, keyed
by path so repeated pricing questions do not re-hit the API.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode

import httpx

from akamai_cloud_mcp.config import Config

# Public Linode API base for the httpx fallback.
LINODE_API_BASE = "https://api.linode.com/v4"

# 24 hours, in seconds.
PRICE_CACHE_TTL = 24 * 60 * 60


class LinodeClientWrapper:
    """GET-only wrapper around the synchronous linode_api4 SDK."""

    def __init__(self, config: Config, token: str | None) -> None:
        self._config = config
        self._token = token
        self._sdk: Any = None
        self._cache: dict[str, tuple[float, Any]] = {}
        # Injected clock so tests can control cache expiry; defaults to wall time.
        self._now = time.monotonic

    # -- SDK access -------------------------------------------------------

    @property
    def sdk(self) -> Any:
        """Return a lazily constructed synchronous LinodeClient."""
        if self._sdk is None:
            if not self._token:
                from akamai_cloud_mcp.auth import MissingTokenError

                raise MissingTokenError(
                    "A Linode token is required for this operation but none was set."
                )
            # Imported lazily so `--help` and tests that never touch the API do
            # not require the SDK to be importable in every environment.
            from linode_api4 import LinodeClient

            self._sdk = LinodeClient(self._token)
        return self._sdk

    # -- Raw GET ----------------------------------------------------------

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Issue a GET against a relative Linode API v4 path via the SDK.

        Reuses the SDK's auth/retry/pagination. The SDK's `get` only performs a
        read; no mutating verb is reachable from here.
        """
        return self.sdk.get(path, filters=None) if params is None else self.sdk.get(
            _with_query(path, params)
        )

    def get_unauthenticated(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a public endpoint with httpx, no token required.

        Used only as a fallback for public catalog endpoints when no token is
        configured. TLS verification stays ON (httpx default).
        """
        url = f"{LINODE_API_BASE}{path if path.startswith('/') else '/' + path}"
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        with httpx.Client(timeout=30.0) as http:
            resp = http.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def public_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a public catalog endpoint, using the token when present.

        Prefers the SDK (auth, retry) when a token is configured, and falls back
        to an unauthenticated httpx GET otherwise, so catalog and pricing
        questions work without account credentials.
        """
        if self._token:
            return self.get(path, params)
        return self.get_unauthenticated(path, params)

    # -- Cached price/type reads -----------------------------------------

    def cached_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a public price/type endpoint, cached for ~24h keyed by path+params.

        Falls back to an unauthenticated httpx GET when no token is configured,
        so catalog/pricing questions work without account credentials.
        """
        key = _with_query(path, params) if params else path
        hit = self._cache.get(key)
        now = self._now()
        if hit is not None and (now - hit[0]) < PRICE_CACHE_TTL:
            return hit[1]
        value = self.public_get(path, params)
        self._cache[key] = (now, value)
        return value

    def clear_cache(self) -> None:
        self._cache.clear()

    # -- Paginated reads --------------------------------------------------

    def get_all(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        """GET every page of an authenticated endpoint and return one flat list.

        Linode list endpoints are paginated; a single GET returns only the first
        page (default 100 rows). The curated list_* tools use this so an account
        with more than one page of a resource is not silently truncated to page 1
        while still reporting the list as complete. Handles both the paginated
        envelope ({data, page, pages}) and a bare-list response.
        """
        base = dict(params or {})
        base["page_size"] = self._config.page_size or 100
        first = self.get(path, {**base, "page": 1})
        if isinstance(first, list):
            return first
        if not isinstance(first, dict):
            return [first]
        rows: list[Any] = list(first.get("data") or [])
        pages = int(first.get("pages") or 1)
        for page in range(2, pages + 1):
            resp = self.get(path, {**base, "page": page})
            if isinstance(resp, dict):
                rows.extend(resp.get("data") or [])
        return rows

    def public_get_all(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        """GET every page of a public endpoint and return one flat list of rows.

        Linode list endpoints are paginated, and a single GET returns only the
        first page. Callers that must see the whole set use this, otherwise rows
        on later pages are silently missed (for example /regions/availability,
        which spans several pages). Handles both the paginated envelope
        ({data, page, pages}) and a bare-list response, and requests the maximum
        page size to keep the round trips down.
        """
        base = dict(params or {})
        base["page_size"] = 500
        first = self.public_get(path, {**base, "page": 1})
        if isinstance(first, list):
            return first
        if not isinstance(first, dict):
            return [first]
        rows: list[Any] = list(first.get("data") or [])
        pages = int(first.get("pages") or 1)
        for page in range(2, pages + 1):
            resp = self.public_get(path, {**base, "page": page})
            if isinstance(resp, dict):
                rows.extend(resp.get("data") or [])
        return rows


def _with_query(path: str, params: dict[str, Any] | None) -> str:
    if not params:
        return path
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}{urlencode(params)}"
