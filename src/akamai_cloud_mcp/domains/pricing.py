"""Pricing & cost domain (tag: pricing).

Tools (Phase 2a/2b): get_pricing, find_gpu_availability, estimate_cost.
All read-only. Built by allowlist serializers and passed through scrub().
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Pricing & cost domain tools on the given FastMCP server."""
    # Tools land in Phase 2a/2b.
    return None
