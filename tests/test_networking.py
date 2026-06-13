"""Phase 6: Networking tools."""

from __future__ import annotations

from typing import Any

from fastmcp.client import Client

from akamai_cloud_mcp.server import build_server


async def _call(mcp: Any, name: str, args: dict[str, Any] | None = None) -> Any:
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
        return result.data


async def _tool_names(mcp: Any) -> set[str]:
    async with Client(mcp) as client:
        return {t.name for t in await client.list_tools()}


async def test_networking_tools_register() -> None:
    names = await _tool_names(build_server(domains="networking"))
    assert {
        "linode_list_firewalls",
        "linode_get_firewall",
        "linode_list_ips",
        "linode_list_vlans",
        "linode_list_vpcs",
        "linode_get_vpc",
        "linode_list_nodebalancers",
    } <= names


async def test_list_firewalls(mock_get: None) -> None:
    data = await _call(build_server(domains="networking"), "linode_list_firewalls")
    assert data["firewalls"][0]["status"] == "enabled"


async def test_get_firewall_includes_rules(mock_get: None) -> None:
    data = await _call(build_server(domains="networking"), "linode_get_firewall", {"firewall_id": 1})
    assert data["id"] == 1
    assert data["rules"]["inbound_policy"] == "DROP"
    rule = data["rules"]["inbound"][0]
    assert rule["ports"] == "22,80,443"
    assert rule["addresses"]["ipv4"] == ["0.0.0.0/0"]
    assert data["entities"][0]["label"] == "web-1"


async def test_list_ips(mock_get: None) -> None:
    data = await _call(build_server(domains="networking"), "linode_list_ips")
    assert data["ips"][0]["address"] == "192.0.2.10"


async def test_list_vlans(mock_get: None) -> None:
    data = await _call(build_server(domains="networking"), "linode_list_vlans")
    assert data["vlans"][0]["cidr"] == "10.0.0.0/24"


async def test_list_vpcs_has_no_subnets(mock_get: None) -> None:
    data = await _call(build_server(domains="networking"), "linode_list_vpcs")
    vpc = data["vpcs"][0]
    assert vpc["id"] == 30
    # The list view does not include subnets; those come from get_vpc.
    assert "subnets" not in vpc


async def test_get_vpc_surfaces_subnets(mock_get: None) -> None:
    data = await _call(build_server(domains="networking"), "linode_get_vpc", {"vpc_id": 30})
    assert data["label"] == "prod-vpc"
    assert len(data["subnets"]) == 2
    labels = {s["label"] for s in data["subnets"]}
    assert labels == {"web", "db"}


async def test_list_nodebalancers(mock_get: None) -> None:
    data = await _call(build_server(domains="networking"), "linode_list_nodebalancers")
    nb = data["nodebalancers"][0]
    assert nb["hostname"].endswith("nodebalancer.linode.com")
    assert nb["transfer"]["total"] == 4.0
