"""DNS (Domains) domain (tag: dns).

Tools: list_domains, get_domain, list_domain_records. All read-only,
allowlist-serialized, and scrubbed. Domains and records carry no secret material;
soa_email is the public zone SOA contact, not account PII. These tools use the
account, so a token is required.
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.domains._helpers import READ_ONLY, cap
from akamai_cloud_mcp.errors import map_api_error
from akamai_cloud_mcp.scrub import scrub
from akamai_cloud_mcp.serialize import serialize_domain, serialize_domain_record


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register DNS tools on the given FastMCP server."""

    @mcp.tool(
        name="list_domains",
        tags={"dns"},
        annotations=READ_ONLY,
        description=(
            "List the DNS domains (zones) managed in the account, with type "
            "(master or slave), status, and SOA email. Use to inventory DNS zones."
        ),
    )
    def list_domains() -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/domains")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "domains": [serialize_domain(r) for r in capped],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} domains."
        return scrub(result)

    @mcp.tool(
        name="get_domain",
        tags={"dns"},
        annotations=READ_ONLY,
        description=(
            "Get one DNS domain (zone) by id, with its type, status, SOA email, "
            "SOA timers, and master/AXFR IPs. Use list_domain_records for its "
            "records."
        ),
    )
    def get_domain(domain_id: int) -> dict[str, Any]:
        try:
            resp = ctx.client.get(f"/domains/{domain_id}")
        except Exception as exc:
            raise map_api_error(exc) from exc
        return scrub(serialize_domain(resp))

    @mcp.tool(
        name="list_domain_records",
        tags={"dns"},
        annotations=READ_ONLY,
        description=(
            "List the DNS records for a domain (A, AAAA, NS, MX, CNAME, TXT, SRV, "
            "PTR, CAA), with name, target, TTL, and priority/weight/port where set."
        ),
    )
    def list_domain_records(domain_id: int) -> dict[str, Any]:
        try:
            rows = ctx.client.get_all(f"/domains/{domain_id}/records")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "domain_id": domain_id,
            "count": len(capped),
            "capped": was_capped,
            "records": [serialize_domain_record(r) for r in capped],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} records."
        return scrub(result)
