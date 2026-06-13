"""Phase 2a: Regions & Catalog and get_pricing tests (mocked SDK boundary)."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp.client import Client
from fastmcp.exceptions import ToolError

from akamai_cloud_mcp.server import build_server


async def _call(mcp: Any, name: str, args: dict[str, Any] | None = None) -> Any:
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
        return result.data


async def _tool_names(mcp: Any) -> set[str]:
    async with Client(mcp) as client:
        return {t.name for t in await client.list_tools()}


async def test_tools_register_under_domains() -> None:
    names = await _tool_names(build_server(domains="regions,pricing"))
    assert {"linode_list_regions", "linode_get_region_availability", "linode_list_instance_types"} <= names
    assert "linode_get_pricing" in names


async def test_domain_toggle_excludes_pricing() -> None:
    names = await _tool_names(build_server(domains="regions"))
    assert "linode_list_regions" in names
    assert "linode_get_pricing" not in names


async def test_list_regions(mock_catalog: None) -> None:
    data = await _call(build_server(domains="regions"), "linode_list_regions")
    assert data["count"] == 2
    ids = {r["id"] for r in data["regions"]}
    assert ids == {"us-east", "id-cgk"}


async def test_list_instance_types_exposes_fields(mock_catalog: None) -> None:
    data = await _call(build_server(domains="regions"), "linode_list_instance_types")
    by_id = {t["id"]: t for t in data["types"]}
    std = by_id["g6-standard-1"]
    assert std["vcpus"] == 1
    assert std["class"] == "standard"
    assert std["gpus"] == 0
    assert std["accelerated_devices"] == 0
    assert std["price"]["monthly"] == 10.0


async def test_region_availability_account_wide(mock_catalog: None) -> None:
    data = await _call(build_server(domains="regions"), "linode_get_region_availability")
    assert data["region"] is None
    assert data["count"] == 2


async def test_region_availability_single_region(mock_catalog: None) -> None:
    data = await _call(
        build_server(domains="regions"), "linode_get_region_availability", {"region": "us-east"}
    )
    assert data["region"] == "us-east"
    assert data["count"] == 1


async def test_get_pricing_region_override(mock_catalog: None) -> None:
    mcp = build_server(domains="pricing")
    data = await _call(mcp, "linode_get_pricing", {"family": "compute", "region": "id-cgk"})
    std = next(i for i in data["items"] if i["id"] == "g6-standard-1")
    # id-cgk has an explicit override.
    assert std["monthly"] == 12.0
    assert std["hourly"] == 0.018


async def test_get_pricing_region_fallback_to_default(mock_catalog: None) -> None:
    mcp = build_server(domains="pricing")
    data = await _call(mcp, "linode_get_pricing", {"family": "compute", "region": "us-east"})
    std = next(i for i in data["items"] if i["id"] == "g6-standard-1")
    # us-east has no override, so it falls back to the top-level price.
    assert std["monthly"] == 10.0
    assert std["hourly"] == 0.015


async def test_get_pricing_null_monthly_stays_null(mock_catalog: None) -> None:
    mcp = build_server(domains="pricing")
    data = await _call(mcp, "linode_get_pricing", {"family": "network_transfer"})
    item = data["items"][0]
    assert item["monthly"] is None
    assert item["hourly"] == 0.01


async def test_get_pricing_object_storage_includes_supplement(mock_catalog: None) -> None:
    mcp = build_server(domains="pricing")
    data = await _call(mcp, "linode_get_pricing", {"family": "object_storage"})
    supp = data["request_pricing_supplement"]
    assert supp["class_a"]["price_per_1000"] == 0.005
    assert supp["class_b"]["free_quota_per_month"] == 12500000


async def test_get_pricing_unknown_family_errors(mock_catalog: None) -> None:
    mcp = build_server(domains="pricing")
    with pytest.raises(ToolError):
        await _call(mcp, "linode_get_pricing", {"family": "bogus"})
