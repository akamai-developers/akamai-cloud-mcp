"""Regions & Catalog domain (tag: regions).

Tools (Phase 2a): list_regions, get_region_availability, list_instance_types.
All read-only. Built by allowlist serializers and passed through scrub().
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Regions & Catalog tools on the given FastMCP server."""
    # Tools land in Phase 2a.
    return None
