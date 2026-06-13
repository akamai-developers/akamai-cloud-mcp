"""Shared error mapping: turn SDK / HTTP failures into clean tool errors.

Tools raise `ToolError` with a model-friendly message. The token is never
included in any message. Rate-limit and auth failures are mapped to plain text
so the model gets a useful, non-leaky explanation.
"""

from __future__ import annotations

from typing import Any


class ToolError(Exception):
    """A clean, model-facing error raised from a tool."""


def map_api_error(exc: Exception) -> ToolError:
    """Map an arbitrary SDK/httpx exception to a clean ToolError.

    Recognizes HTTP status via common attributes without importing every SDK
    error type. Honors Retry-After when the underlying response exposes it.
    """
    status = _status_of(exc)
    retry_after = _retry_after_of(exc)

    if status == 401:
        return ToolError(
            "Authentication failed (401). Check that LINODE_TOKEN is set and the "
            "token is valid and unexpired."
        )
    if status == 403:
        return ToolError(
            "Access denied (403). The token is missing a required read scope for "
            "this resource."
        )
    if status == 404:
        return ToolError("Not found (404). The requested resource does not exist.")
    if status == 429:
        hint = f" Retry after {retry_after} seconds." if retry_after else ""
        return ToolError(
            "Rate limited (429) by the Linode API." + hint + " Try again shortly."
        )
    if status is not None and status >= 500:
        return ToolError(f"Linode API server error ({status}). Try again later.")

    # Fall back to a generic message; never echo token-shaped content.
    from akamai_cloud_mcp.scrub import scrub_text

    return ToolError(scrub_text(f"Request failed: {exc}"))


def _status_of(exc: Exception) -> int | None:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
    # linode_api4 ApiError carries .status
    return None


def _retry_after_of(exc: Exception) -> Any:
    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
        if headers is not None:
            try:
                return headers.get("Retry-After")
            except Exception:
                return None
    return None
