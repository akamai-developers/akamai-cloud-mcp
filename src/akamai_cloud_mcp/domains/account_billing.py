"""Account & Billing domain (tag: account).

Tools: get_account, get_account_transfer, list_invoices, list_events,
get_account_limits. PII and payment fields are redacted on every return. This
domain is on by default but can be toggled off with --domains.
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.domains._helpers import READ_ONLY, Detail, cap, project
from akamai_cloud_mcp.errors import map_api_error
from akamai_cloud_mcp.scrub import scrub
from akamai_cloud_mcp.serialize import serialize_account, serialize_event, serialize_invoice

# Published Linode API rate limits. There is no per-account limits endpoint, so
# these are documented here and surfaced by get_account_limits. Update from the
# Linode API rate-limit docs.
PUBLISHED_RATE_LIMITS = [
    {"scope": "GET collections (most list endpoints)", "limit": "200 requests/minute"},
    {"scope": "Images list", "limit": "20 requests/minute"},
    {"scope": "StackScripts", "limit": "60 requests/minute"},
    {"scope": "Object Storage", "limit": "60 requests/minute"},
    {"scope": "Other operations", "limit": "1600 requests/minute"},
]
RATE_LIMITS_SOURCE = "Linode API rate-limit documentation"


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Account & Billing tools on the given FastMCP server."""

    @mcp.tool(
        name="linode_get_account",
        tags={"account"},
        annotations=READ_ONLY,
        description=(
            "Get account-level details (company, country, balance, capabilities). "
            "Payment-method and personal fields (card, email, phone, billing "
            "address) are redacted."
        ),
    )
    def get_account() -> dict[str, Any]:
        try:
            resp = ctx.client.get("/account")
        except Exception as exc:
            raise map_api_error(exc) from exc
        return scrub(serialize_account(resp))

    @mcp.tool(
        name="linode_get_account_transfer",
        tags={"account"},
        annotations=READ_ONLY,
        description=(
            "Get the account's network transfer for the current billing period: "
            "used, quota, and billable GB, plus per-region transfer."
        ),
    )
    def get_account_transfer() -> dict[str, Any]:
        try:
            resp = ctx.client.get("/account/transfer")
        except Exception as exc:
            raise map_api_error(exc) from exc
        return scrub(resp)

    @mcp.tool(
        name="linode_list_invoices",
        tags={"account"},
        annotations=READ_ONLY,
        description=(
            "List the account's invoices with date, subtotal, tax, and total. "
            "Payment-method detail is redacted."
        ),
    )
    def list_invoices(detail: Detail | None = None) -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/account/invoices")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "invoices": [
                project(serialize_invoice(r), detail or ctx.config.detail) for r in capped
            ],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} invoices."
        return scrub(result)

    @mcp.tool(
        name="linode_list_events",
        tags={"account"},
        annotations=READ_ONLY,
        description=(
            "List recent account events (the audit log): actions, the entity each "
            "affected, status, and timestamps."
        ),
    )
    def list_events(detail: Detail | None = None) -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/account/events")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "events": [
                project(serialize_event(r), detail or ctx.config.detail) for r in capped
            ],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} events."
        return scrub(result)

    @mcp.tool(
        name="linode_get_account_limits",
        tags={"account"},
        annotations=READ_ONLY,
        description=(
            "Summarize the account limits that apply. Linode does not expose a "
            "single per-account service-limit endpoint, so this composes the "
            "published API rate limits, the Object Storage quotas (the only quota "
            "API Linode exposes), and the network transfer pool."
        ),
    )
    def get_account_limits() -> dict[str, Any]:
        result: dict[str, Any] = {
            "summary": (
                "Linode does not expose a single per-account service-limit "
                "endpoint. The values below are the published API rate limits, the "
                "Object Storage quotas, and the network transfer pool that apply to "
                "this account."
            ),
            "rate_limits": {"source": RATE_LIMITS_SOURCE, "limits": PUBLISHED_RATE_LIMITS},
        }

        # Object Storage quotas are the only quota API Linode exposes.
        try:
            quotas = ctx.client.get_all("/object-storage/quotas")
            result["object_storage_quotas"] = quotas[: ctx.config.max_results]
        except Exception:
            result["object_storage_quotas"] = None
            result.setdefault("warnings", []).append(
                "Could not load Object Storage quotas (token may lack scope)."
            )

        # Network transfer pool.
        try:
            transfer = ctx.client.get("/account/transfer")
            result["transfer_pool"] = transfer
        except Exception:
            result["transfer_pool"] = None
            result.setdefault("warnings", []).append(
                "Could not load the network transfer pool (token may lack scope)."
            )

        return scrub(result)
