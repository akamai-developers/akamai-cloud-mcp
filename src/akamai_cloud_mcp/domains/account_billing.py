"""Account & Billing domain (tag: account).

Tools (Phase 7): get_account, get_account_transfer, list_invoices, list_events, get_account_limits.
All read-only. Built by allowlist serializers and passed through scrub().
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Account & Billing domain tools on the given FastMCP server."""
    # Tools land in Phase 7.
    return None
