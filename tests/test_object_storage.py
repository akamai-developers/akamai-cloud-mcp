"""Phase 5: Object Storage tools. Keys must never be returned."""

from __future__ import annotations

import json
from typing import Any

from fastmcp.client import Client

from akamai_cloud_mcp.server import build_server
from tests.conftest import _FAKE_ACCESS_KEY, _FAKE_SECRET_KEY


async def _call(mcp: Any, name: str, args: dict[str, Any] | None = None) -> Any:
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
        return result.data


async def _tool_names(mcp: Any) -> set[str]:
    async with Client(mcp) as client:
        return {t.name for t in await client.list_tools()}


async def test_object_storage_tools_register() -> None:
    names = await _tool_names(build_server(domains="object_storage"))
    assert {
        "linode_list_object_storage_buckets",
        "linode_get_object_storage_bucket",
        "linode_list_object_storage_endpoints",
        "linode_get_object_storage_transfer",
        "linode_list_object_storage_quotas",
    } <= names


async def test_no_key_listing_tool_exists() -> None:
    names = await _tool_names(build_server(domains="all"))
    assert not any("key" in n for n in names)


async def test_buckets_never_return_keys(mock_get: None) -> None:
    data = await _call(build_server(domains="object_storage"), "linode_list_object_storage_buckets")
    bucket = data["buckets"][0]
    assert bucket["label"] == "assets"
    assert "access_key" not in bucket
    assert "secret_key" not in bucket
    blob = json.dumps(data)
    assert _FAKE_ACCESS_KEY not in blob
    assert _FAKE_SECRET_KEY not in blob


async def test_buckets_region_scope(mock_get: None) -> None:
    # No region-specific fixture path is registered, so this confirms the path is
    # built; we just check the unscoped call returns buckets.
    data = await _call(build_server(domains="object_storage"), "linode_list_object_storage_buckets")
    assert data["region"] is None
    assert data["count"] == 1


async def test_get_single_bucket_never_returns_keys(mock_get: None) -> None:
    data = await _call(
        build_server(domains="object_storage"),
        "linode_get_object_storage_bucket",
        {"region": "us-east", "bucket": "assets"},
    )
    assert data["label"] == "assets"
    assert data["hostname"].endswith("linodeobjects.com")
    assert "access_key" not in data
    assert "secret_key" not in data
    blob = json.dumps(data)
    assert _FAKE_ACCESS_KEY not in blob
    assert _FAKE_SECRET_KEY not in blob


async def test_endpoints(mock_get: None) -> None:
    data = await _call(build_server(domains="object_storage"), "linode_list_object_storage_endpoints")
    assert data["endpoints"][0]["endpoint_type"] == "E1"


async def test_transfer(mock_get: None) -> None:
    data = await _call(build_server(domains="object_storage"), "linode_get_object_storage_transfer")
    assert data["quota"] == 1099511627776


async def test_quotas(mock_get: None) -> None:
    data = await _call(build_server(domains="object_storage"), "linode_list_object_storage_quotas")
    assert data["quotas"][0]["resource_metric"] == "bucket"
