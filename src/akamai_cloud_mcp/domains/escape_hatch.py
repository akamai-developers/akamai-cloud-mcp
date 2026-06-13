"""Escape hatch domain (tag: escape).

One generic read-only tool, linode_api_get, reaches any Linode API v4 path the
curated tools do not cover. This keeps the curated surface small.

Defense in depth:
1. The method is hardcoded to GET (the tool only calls ctx.client.get).
2. The path is validated: relative v4 path only, no absolute URL to another host,
   no traversal.
3. A path denylist rejects known secret-returning endpoints outright, before any
   fetch, so they cannot even be reached to be scrubbed.
4. The result runs through the recursive scrub() as a final backstop.
"""

from __future__ import annotations

import fnmatch
from typing import Any

from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.domains._helpers import READ_ONLY
from akamai_cloud_mcp.errors import ToolError, map_api_error
from akamai_cloud_mcp.scrub import scrub

# Paths the escape hatch refuses outright (matched case-insensitively against the
# normalized path, without query string).
DENYLIST_PATTERNS = (
    "/lke/clusters/*/kubeconfig",
    "/object-storage/keys",
    "/object-storage/keys/*",
    "/profile/tokens",
    "/profile/tokens/*",
    "/account/payment-methods",
    "/account/payment-methods/*",
)


def normalize_path(raw: str) -> str:
    """Validate and normalize a Linode API v4 relative path.

    Raises ToolError on an absolute URL, a protocol-relative host, traversal, or
    an empty path. Returns a path with a single leading slash and no /v4 prefix.
    """
    if raw is None or not str(raw).strip():
        raise ToolError("path is required.")
    path = str(raw).strip()

    lowered = path.lower()
    if "://" in lowered or lowered.startswith("//"):
        raise ToolError("Absolute URLs are not allowed. Pass a relative v4 path, e.g. /regions.")
    if ".." in path:
        raise ToolError("Path traversal ('..') is not allowed.")

    if not path.startswith("/"):
        path = "/" + path
    # Strip an optional /v4 prefix; the client base already includes it.
    if path.lower().startswith("/v4/"):
        path = path[3:]
    elif path.lower() == "/v4":
        path = "/"
    return path


def is_denied(path: str) -> bool:
    """Return True if the normalized path matches a denylisted secret endpoint."""
    candidate = path.split("?", 1)[0].lower().rstrip("/")
    for pattern in DENYLIST_PATTERNS:
        if fnmatch.fnmatch(candidate, pattern):
            return True
    return False


# The escape hatch returns raw API objects, which can be large. Cap the row count
# so a broad path does not dump a huge payload into a smaller model's context.
RAW_ITEM_CAP = 50


def cap_raw(resp: Any) -> Any:
    """Truncate a large `data` list in a raw response, leaving a note."""
    if isinstance(resp, dict) and isinstance(resp.get("data"), list):
        rows = resp["data"]
        if len(rows) > RAW_ITEM_CAP:
            out = dict(resp)
            out["data"] = rows[:RAW_ITEM_CAP]
            out["_truncated"] = (
                f"Showing {RAW_ITEM_CAP} of {len(rows)} items. Narrow with query "
                "params (for example page_size) or use a curated tool."
            )
            return out
    return resp


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register the escape-hatch tool on the given FastMCP server."""

    @mcp.tool(
        name="linode_api_get",
        tags={"escape"},
        annotations=READ_ONLY,
        description=(
            "Read-only escape hatch: perform a GET against any Linode API v4 path "
            "not covered by a curated tool, for example '/images' or "
            "'/databases/engines'. Only GET is allowed. Pass a relative v4 path "
            "and optional query params. Known secret-returning endpoints "
            "(kubeconfig, object storage keys, profile tokens, payment methods) "
            "are refused. The response is scrubbed of secrets."
        ),
    )
    def linode_api_get(path: str, params: dict[str, Any] | None = None) -> Any:
        normalized = normalize_path(path)
        if is_denied(normalized):
            raise ToolError(
                "That path is denied because it can return secret material "
                "(kubeconfig, keys, tokens, or payment methods). It is blocked by "
                "design."
            )
        try:
            resp = ctx.client.get(normalized, params)
        except Exception as exc:
            raise map_api_error(exc) from exc
        return scrub(cap_raw(resp))
