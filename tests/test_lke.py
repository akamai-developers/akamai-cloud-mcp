"""Phase 4: LKE tools. The kubeconfig must never be returned."""

from __future__ import annotations

import json
from typing import Any

from fastmcp.client import Client

from akamai_cloud_mcp.server import build_server
from tests.conftest import _FAKE_KUBECONFIG_B64


async def _call(mcp: Any, name: str, args: dict[str, Any] | None = None) -> Any:
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
        return result.data


async def _tool_names(mcp: Any) -> set[str]:
    async with Client(mcp) as client:
        return {t.name for t in await client.list_tools()}


def _has_key(obj: Any, key: str) -> bool:
    if isinstance(obj, dict):
        return key in obj or any(_has_key(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_key(v, key) for v in obj)
    return False


async def test_lke_tools_register() -> None:
    names = await _tool_names(build_server(domains="lke"))
    assert {
        "linode_list_lke_clusters",
        "linode_get_lke_cluster",
        "linode_list_kubernetes_versions",
    } <= names


async def test_list_clusters_no_kubeconfig(mock_get: None) -> None:
    data = await _call(build_server(domains="lke"), "linode_list_lke_clusters")
    assert data["count"] == 1
    cluster = data["clusters"][0]
    assert cluster["id"] == 555
    assert "kubeconfig" not in cluster
    # The planted kubeconfig value must not appear anywhere in the output.
    assert _FAKE_KUBECONFIG_B64 not in json.dumps(data)


async def test_get_cluster_composes_subresources(mock_get: None) -> None:
    data = await _call(build_server(domains="lke"), "linode_get_lke_cluster", {"cluster_id": 555})
    assert data["cluster"]["label"] == "prod-cluster"
    assert data["pools"][0]["count"] == 3
    assert data["api_endpoints"][0]["endpoint"].endswith(":443")
    assert data["control_plane_acl"]["enabled"] is True
    # dashboard URL is intentionally no longer fetched (deprecated endpoint).
    assert "dashboard_url" not in data


async def test_get_cluster_never_returns_kubeconfig(mock_get: None) -> None:
    data = await _call(build_server(domains="lke"), "linode_get_lke_cluster", {"cluster_id": 555})
    assert not _has_key(data, "kubeconfig")
    assert _FAKE_KUBECONFIG_B64 not in json.dumps(data)


async def test_list_kubernetes_versions(mock_get: None) -> None:
    data = await _call(build_server(domains="lke"), "linode_list_kubernetes_versions")
    ids = {v["id"] for v in data["versions"]}
    assert ids == {"1.31", "1.30"}
