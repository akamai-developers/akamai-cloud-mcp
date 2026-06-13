"""Phase 3: Compute tools (mocked at the SDK sync boundary)."""

from __future__ import annotations

from typing import Any

from fastmcp.client import Client

from akamai_cloud_mcp.config import Config
from akamai_cloud_mcp.server import build_server


async def _call(mcp: Any, name: str, args: dict[str, Any] | None = None) -> Any:
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
        return result.data


async def _tool_names(mcp: Any) -> set[str]:
    async with Client(mcp) as client:
        return {t.name for t in await client.list_tools()}


async def test_compute_tools_register() -> None:
    names = await _tool_names(build_server(domains="compute"))
    assert {"linode_list_instances", "linode_get_instance", "linode_list_volumes"} <= names


async def test_compute_domain_toggle_off() -> None:
    names = await _tool_names(build_server(domains="pricing"))
    assert "linode_list_instances" not in names


async def test_list_instances_shape(mock_get: None) -> None:
    data = await _call(build_server(domains="compute"), "linode_list_instances")
    assert data["count"] == 2
    first = data["instances"][0]
    assert first["id"] == 111
    assert first["label"] == "web-1"
    assert first["ipv4"] == ["192.0.2.10"]
    # Non-allowlisted field must not leak.
    assert "alerts" not in first


async def test_list_instances_concise(mock_get: None) -> None:
    data = await _call(
        build_server(domains="compute"), "linode_list_instances", {"detail": "concise"}
    )
    first = data["instances"][0]
    # Identity/routing fields are kept...
    assert first["id"] == 111
    assert first["label"] == "web-1"
    assert first["region"] == "us-east"
    assert first["type"] == "g6-standard-1"
    assert first["status"] == "running"
    # ...bulky fields are dropped to keep a long list cheap.
    assert "ipv4" not in first
    assert "specs" not in first
    assert "image" not in first


async def test_detail_default_from_config(mock_get: None) -> None:
    # A deploy-wide concise default (--detail concise) applies when the caller
    # does not specify, and an explicit detail=full overrides it per call.
    mcp = build_server(domains="compute", config=Config(detail="concise"))
    default = await _call(mcp, "linode_list_instances")
    assert "ipv4" not in default["instances"][0]
    override = await _call(mcp, "linode_list_instances", {"detail": "full"})
    assert override["instances"][0]["ipv4"] == ["192.0.2.10"]


async def test_get_instance_shape(mock_get: None) -> None:
    data = await _call(build_server(domains="compute"), "linode_get_instance", {"instance_id": 111})
    assert data["id"] == 111
    assert data["region"] == "us-east"
    assert data["specs"]["vcpus"] == 1


async def test_list_volumes_shape(mock_get: None) -> None:
    data = await _call(build_server(domains="compute"), "linode_list_volumes")
    assert data["count"] == 1
    vol = data["volumes"][0]
    assert vol["size"] == 100
    assert vol["linode_id"] == 111


async def test_list_instances_capping(mock_get: None) -> None:
    config = Config(max_results=1)
    mcp = build_server(domains="compute", config=config)
    data = await _call(mcp, "linode_list_instances")
    assert data["count"] == 1
    assert data["capped"] is True
    assert "note" in data
