"""Networking domain (tag: networking).

Tools: list_firewalls, list_ips, list_vlans, list_vpcs, get_vpc,
list_nodebalancers. All read-only, allowlist-serialized, scrubbed.

IPs are returnable (the account owns them) but never logged. Deprecated IP
assign/share operations are not exposed (and would be writes anyway).
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.domains._helpers import READ_ONLY, cap
from akamai_cloud_mcp.errors import map_api_error
from akamai_cloud_mcp.scrub import scrub
from akamai_cloud_mcp.serialize import (
    serialize_firewall,
    serialize_ip,
    serialize_nodebalancer,
    serialize_subnet,
    serialize_vlan,
    serialize_vpc,
)


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Networking tools on the given FastMCP server."""

    def _list(path: str, key: str, serializer: Any) -> dict[str, Any]:
        try:
            rows = ctx.client.get_all(path)
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            key: [serializer(r) for r in capped],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} rows."
        return scrub(result)

    @mcp.tool(
        name="list_firewalls",
        tags={"networking"},
        annotations=READ_ONLY,
        description="List Cloud Firewalls with their rules, status, and attached entities.",
    )
    def list_firewalls() -> dict[str, Any]:
        return _list("/networking/firewalls", "firewalls", serialize_firewall)

    @mcp.tool(
        name="list_ips",
        tags={"networking"},
        annotations=READ_ONLY,
        description=(
            "List the IP addresses on the account, with type, region, reverse DNS, "
            "and the instance each is assigned to."
        ),
    )
    def list_ips() -> dict[str, Any]:
        return _list("/networking/ips", "ips", serialize_ip)

    @mcp.tool(
        name="list_vlans",
        tags={"networking"},
        annotations=READ_ONLY,
        description="List VLANs with their region, CIDR, and attached instances.",
    )
    def list_vlans() -> dict[str, Any]:
        return _list("/networking/vlans", "vlans", serialize_vlan)

    @mcp.tool(
        name="list_vpcs",
        tags={"networking"},
        annotations=READ_ONLY,
        description=(
            "List VPCs with their region and description. Subnets are returned by "
            "get_vpc, not here."
        ),
    )
    def list_vpcs() -> dict[str, Any]:
        return _list("/vpcs", "vpcs", serialize_vpc)

    @mcp.tool(
        name="get_vpc",
        tags={"networking"},
        annotations=READ_ONLY,
        description="Get one VPC by id, including its subnets and the instances in each subnet.",
    )
    def get_vpc(vpc_id: int) -> dict[str, Any]:
        try:
            detail = ctx.client.get(f"/vpcs/{vpc_id}")
        except Exception as exc:
            raise map_api_error(exc) from exc
        result = serialize_vpc(detail)
        subnets = detail.get("subnets") if isinstance(detail, dict) else None
        result["subnets"] = [serialize_subnet(s) for s in (subnets or [])]
        return scrub(result)

    @mcp.tool(
        name="list_nodebalancers",
        tags={"networking"},
        annotations=READ_ONLY,
        description=(
            "List NodeBalancers with their region, hostname, IPs, and transfer "
            "usage."
        ),
    )
    def list_nodebalancers() -> dict[str, Any]:
        return _list("/nodebalancers", "nodebalancers", serialize_nodebalancer)
