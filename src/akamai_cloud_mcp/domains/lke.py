"""LKE domain (tag: lke).

Tools (Phase 4): list_lke_clusters, get_lke_cluster, list_kubernetes_versions.
All read-only. Built by allowlist serializers and passed through scrub().
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register LKE domain tools on the given FastMCP server."""
    # Tools land in Phase 4.
    return None
