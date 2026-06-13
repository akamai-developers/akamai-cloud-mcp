"""Escape hatch domain (tag: escape).

Tools (Phase 8): linode_api_get.
All read-only. Built by allowlist serializers and passed through scrub().
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Escape hatch domain tools on the given FastMCP server."""
    # Tools land in Phase 8.
    return None
