"""Object Storage domain (tag: object_storage).

Tools (Phase 5): list_object_storage_buckets, list_object_storage_endpoints,
get_object_storage_transfer, list_object_storage_quotas.
All read-only. Built by allowlist serializers and passed through scrub().
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Object Storage domain tools on the given FastMCP server."""
    # Tools land in Phase 5.
    return None
