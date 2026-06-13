"""Regression tests for find_gpu_availability pagination and per-region lookup.

Both bugs made GPU plans look out of stock:
- /regions/availability is paginated; reading only page 1 missed available rows.
- the per-region endpoint omits the region field, so those rows were dropped.
"""

from __future__ import annotations

from typing import Any

from fastmcp.client import Client

from akamai_cloud_mcp import client as client_mod
from akamai_cloud_mcp.server import build_server

GPU_TYPES = {
    "data": [
        {
            "id": "g2-gpu-rtx4000a1-s",
            "label": "RTX4000 Ada x1 Small",
            "class": "gpu",
            "vcpus": 8,
            "memory": 16384,
            "gpus": 1,
            "accelerated_devices": 0,
            "price": {"hourly": 0.52, "monthly": 350.0},
            "region_prices": [],
        }
    ]
}


async def _call(mcp: Any, name: str, args: dict[str, Any] | None = None) -> Any:
    async with Client(mcp) as client:
        return (await client.call_tool(name, args or {})).data


async def test_find_gpu_availability_reads_all_pages(monkeypatch: Any) -> None:
    """The GPU is available only on page 2, so a single-page read would miss it."""

    def fake_cached_get(self: Any, path: str, params: Any = None) -> Any:
        return GPU_TYPES

    def fake_public_get(self: Any, path: str, params: Any = None) -> Any:
        page = (params or {}).get("page", 1)
        if path == "/regions/availability":
            if page == 1:
                return {
                    "data": [{"region": "us-east", "plan": "g6-standard-1", "available": True}],
                    "page": 1,
                    "pages": 2,
                }
            return {
                "data": [
                    {"region": "eu-central", "plan": "g2-gpu-rtx4000a1-s", "available": True}
                ],
                "page": 2,
                "pages": 2,
            }
        raise KeyError(path)

    monkeypatch.setattr(client_mod.LinodeClientWrapper, "cached_get", fake_cached_get)
    monkeypatch.setattr(client_mod.LinodeClientWrapper, "public_get", fake_public_get)

    data = await _call(build_server(domains="pricing"), "find_gpu_availability")
    plans = {p["id"]: p for p in data["gpu_plans"]}
    assert plans["g2-gpu-rtx4000a1-s"]["available_regions"] == ["eu-central"]


async def test_find_gpu_availability_per_region_without_region_field(monkeypatch: Any) -> None:
    """The per-region endpoint returns a bare list with no region field."""

    def fake_cached_get(self: Any, path: str, params: Any = None) -> Any:
        return GPU_TYPES

    def fake_public_get(self: Any, path: str, params: Any = None) -> Any:
        if path == "/regions/eu-central/availability":
            return [{"plan": "g2-gpu-rtx4000a1-s", "available": True}]
        raise KeyError(path)

    monkeypatch.setattr(client_mod.LinodeClientWrapper, "cached_get", fake_cached_get)
    monkeypatch.setattr(client_mod.LinodeClientWrapper, "public_get", fake_public_get)

    data = await _call(
        build_server(domains="pricing"), "find_gpu_availability", {"region": "eu-central"}
    )
    plans = {p["id"]: p for p in data["gpu_plans"]}
    assert plans["g2-gpu-rtx4000a1-s"]["available_regions"] == ["eu-central"]
