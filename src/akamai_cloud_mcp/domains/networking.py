"""Networking domain (tag: networking).

Tools (Phase 6): list_firewalls, list_ips, list_vlans, list_vpcs, get_vpc, list_nodebalancers.
All read-only. Built by allowlist serializers and passed through scrub().
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Networking domain tools on the given FastMCP server."""
    # Tools land in Phase 6.
    return None
