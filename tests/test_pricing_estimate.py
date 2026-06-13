"""Phase 2b: find_gpu_availability, estimate_cost (golden), and staleness diff."""

from __future__ import annotations

from typing import Any

from fastmcp.client import Client

from akamai_cloud_mcp.server import build_server
from akamai_cloud_mcp.staleness import diff_prices

# The golden sample stack. The README worked example must match this.
GOLDEN_STACK = {
    "request": {
        "region": "us-east",
        "instances": [{"type": "g6-standard-1", "count": 1, "backups": True}],
        "volumes": [{"size_gb": 100, "count": 1}],
        "nodebalancers": 1,
        "lke_tier": "ha",
        "object_storage": {
            "storage_gb": 500,
            "class_a_requests": 2000000,
            "class_b_requests": 12500000,
            "egress_gb": 0,
        },
        "extra_egress_gb": 0,
    }
}


async def _call(mcp: Any, name: str, args: dict[str, Any] | None = None) -> Any:
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
        return result.data


# -- find_gpu_availability ------------------------------------------------


async def test_gpu_and_accelerated_both_returned(mock_catalog: None) -> None:
    data = await _call(build_server(domains="pricing"), "find_gpu_availability")
    gpu_ids = {p["id"] for p in data["gpu_plans"]}
    accel_ids = {p["id"] for p in data["accelerated_plans"]}
    assert "g2-gpu-rtx4000a1-s" in gpu_ids
    assert "accelerated-netint-1" in accel_ids
    # The accelerated plan must NOT appear in gpu_plans (gpus == 0).
    assert "accelerated-netint-1" not in gpu_ids


async def test_gpu_excludes_standard_plans(mock_catalog: None) -> None:
    data = await _call(build_server(domains="pricing"), "find_gpu_availability")
    all_ids = {p["id"] for p in data["gpu_plans"] + data["accelerated_plans"]}
    assert "g6-standard-1" not in all_ids


async def test_gpu_marketing_only_flagged(mock_catalog: None) -> None:
    data = await _call(build_server(domains="pricing"), "find_gpu_availability")
    marketing_ids = {p["id"] for p in data["marketing_only"]}
    assert "rtx-pro-6000-blackwell" in marketing_ids


async def test_gpu_availability_per_region(mock_catalog: None) -> None:
    data = await _call(
        build_server(domains="pricing"), "find_gpu_availability", {"region": "us-east"}
    )
    gpu = next(p for p in data["gpu_plans"] if p["id"] == "g2-gpu-rtx4000a1-s")
    assert "us-east" in gpu["available_regions"]


# -- estimate_cost golden -------------------------------------------------


async def test_estimate_cost_golden(mock_catalog: None) -> None:
    data = await _call(build_server(domains="pricing"), "estimate_cost", GOLDEN_STACK)
    by_cat = {line["category"]: line for line in data["lines"]}

    assert by_cat["instance"]["monthly"] == 10.0
    assert by_cat["backups"]["monthly"] == 2.5
    assert by_cat["volume"]["monthly"] == 10.0
    assert by_cat["nodebalancer"]["monthly"] == 10.0
    assert by_cat["lke_control_plane"]["monthly"] == 60.0
    # 250GB billable storage over the 250GB included allotment, at 0.02/GB.
    assert by_cat["object_storage_storage"]["monthly"] == 5.0
    # 1,000,000 class A over the 1,000,000 free quota, at 0.005/1000.
    assert by_cat["object_storage_class_a"]["monthly"] == 5.0
    # class B exactly at the free quota: no overage.
    assert by_cat["object_storage_class_b"]["monthly"] == 0.0

    assert data["total_monthly"] == 102.5
    assert data["total_hourly"] == 0.152698
    assert data["currency"] == "USD"


async def test_estimate_cost_sources_labeled(mock_catalog: None) -> None:
    data = await _call(build_server(domains="pricing"), "estimate_cost", GOLDEN_STACK)
    by_cat = {line["category"]: line for line in data["lines"]}
    assert by_cat["instance"]["source"] == "live API"
    assert by_cat["lke_control_plane"]["source"] == "live API"
    assert by_cat["object_storage_storage"]["source"] == "curated supplement"
    assert by_cat["object_storage_class_a"]["source"] == "curated supplement"


async def test_estimate_cost_totals_match_lines(mock_catalog: None) -> None:
    data = await _call(build_server(domains="pricing"), "estimate_cost", GOLDEN_STACK)
    assert round(sum(line["monthly"] for line in data["lines"]), 4) == data["total_monthly"]


async def test_estimate_cost_free_allotment_before_overage(mock_catalog: None) -> None:
    # storage below the included 250GB should produce zero storage overage.
    stack = {"request": {"object_storage": {"storage_gb": 100}}}
    data = await _call(build_server(domains="pricing"), "estimate_cost", stack)
    storage = next(line for line in data["lines"] if line["category"] == "object_storage_storage")
    assert storage["monthly"] == 0.0


# -- staleness diff (mock mode only exercises the code path) ---------------


def test_staleness_no_drift_against_matching_baseline() -> None:
    current = [{"id": "g6-standard-1", "price": {"hourly": 0.015, "monthly": 10.0}}]
    baseline = {"g6-standard-1": {"hourly": 0.015, "monthly": 10.0}}
    assert diff_prices(current, baseline) == []


def test_staleness_detects_price_change() -> None:
    current = [{"id": "g6-standard-1", "price": {"hourly": 0.018, "monthly": 12.0}}]
    baseline = {"g6-standard-1": {"hourly": 0.015, "monthly": 10.0}}
    changes = diff_prices(current, baseline)
    assert changes == [
        {
            "id": "g6-standard-1",
            "change": "price_changed",
            "was": {"hourly": 0.015, "monthly": 10.0},
            "now": {"hourly": 0.018, "monthly": 12.0},
        }
    ]


def test_staleness_detects_added_and_removed() -> None:
    current = [{"id": "new-plan", "price": {"hourly": 1.0, "monthly": 700.0}}]
    baseline = {"old-plan": {"hourly": 0.5, "monthly": 350.0}}
    changes = diff_prices(current, baseline)
    kinds = {(c["id"], c["change"]) for c in changes}
    assert ("old-plan", "removed") in kinds
    assert ("new-plan", "added") in kinds
