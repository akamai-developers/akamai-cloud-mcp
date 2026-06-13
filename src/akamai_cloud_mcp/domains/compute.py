"""Compute domain (tag: compute).

Tools (Phase 3): list_instances, get_instance, list_volumes.
All read-only. Built by allowlist serializers and passed through scrub().
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Compute domain tools on the given FastMCP server."""
    # Tools land in Phase 3.
    return None
