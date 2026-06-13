"""DNS (Domains) tools. soa_email is the public zone contact and must survive."""

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


async def test_dns_tools_register() -> None:
    names = await _tool_names(build_server(domains="dns"))
    assert {"list_domains", "get_domain", "list_domain_records"} <= names


async def test_dns_domain_toggle_off() -> None:
    names = await _tool_names(build_server(domains="compute"))
    assert "list_domains" not in names


async def test_list_domains_shape(mock_get: None) -> None:
    data = await _call(build_server(domains="dns"), "list_domains")
    assert data["count"] == 1
    dom = data["domains"][0]
    assert dom["domain"] == "example.com"
    assert dom["type"] == "master"
    # soa_email is the public zone contact and must survive scrub (it is not the
    # exact key "email", which scrub redacts).
    assert dom["soa_email"] == "admin@example.com"


async def test_get_domain_shape(mock_get: None) -> None:
    data = await _call(build_server(domains="dns"), "get_domain", {"domain_id": 1})
    assert data["domain"] == "example.com"
    assert data["soa_email"] == "admin@example.com"


async def test_list_domain_records(mock_get: None) -> None:
    data = await _call(build_server(domains="dns"), "list_domain_records", {"domain_id": 1})
    assert data["domain_id"] == 1
    assert data["count"] == 2
    types = {r["type"] for r in data["records"]}
    assert {"A", "MX"} <= types
