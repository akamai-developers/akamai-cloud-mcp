"""Shared test fixtures and Linode API mocks.

The Linode SDK is synchronous. We mock at that sync boundary by patching the
GET-only client wrapper methods to return plain dicts. We never wrap sync SDK
methods in AsyncMock (that returns un-awaited coroutines and breaks the SDK).
"""

from __future__ import annotations

from typing import Any

import pytest

from akamai_cloud_mcp import client as client_mod

# -- Catalog fixtures ----------------------------------------------------

REGIONS = {
    "data": [
        {
            "id": "us-east",
            "label": "Newark, NJ",
            "country": "us",
            "capabilities": ["Linodes", "Kubernetes", "Object Storage"],
            "status": "ok",
            "site_type": "core",
        },
        {
            "id": "id-cgk",
            "label": "Jakarta, ID",
            "country": "id",
            "capabilities": ["Linodes"],
            "status": "ok",
            "site_type": "core",
        },
    ]
}

# One standard plan with a region override (id-cgk costs more) plus backups addon.
LINODE_TYPES = {
    "data": [
        {
            "id": "g6-standard-1",
            "label": "Linode 2GB",
            "class": "standard",
            "vcpus": 1,
            "memory": 2048,
            "disk": 51200,
            "transfer": 2000,
            "network_out": 2000,
            "gpus": 0,
            "accelerated_devices": 0,
            "price": {"hourly": 0.015, "monthly": 10.0},
            "region_prices": [{"id": "id-cgk", "hourly": 0.018, "monthly": 12.0}],
            "addons": {
                "backups": {
                    "price": {"hourly": 0.004, "monthly": 2.5},
                    "region_prices": [{"id": "id-cgk", "hourly": 0.005, "monthly": 3.0}],
                }
            },
        },
        {
            "id": "g2-gpu-rtx4000a1-s",
            "label": "RTX4000 Ada x1 Small",
            "class": "gpu",
            "vcpus": 8,
            "memory": 16384,
            "disk": 524288,
            "transfer": 5000,
            "network_out": 5000,
            "gpus": 1,
            "accelerated_devices": 0,
            "price": {"hourly": 0.52, "monthly": 350.0},
            "region_prices": [],
            "addons": {},
        },
        {
            "id": "accelerated-netint-1",
            "label": "NETINT VPU x1",
            "class": "accelerated",
            "vcpus": 4,
            "memory": 8192,
            "disk": 262144,
            "transfer": 4000,
            "network_out": 4000,
            "gpus": 0,
            "accelerated_devices": 1,
            "price": {"hourly": 0.30, "monthly": 200.0},
            "region_prices": [],
            "addons": {},
        },
    ]
}

# Metered SKU: monthly is null and must stay null.
NETWORK_TRANSFER_PRICES = {
    "data": [
        {
            "id": "distributed_network_transfer",
            "label": "Distributed Network Transfer",
            "price": {"hourly": 0.01, "monthly": None},
            "region_prices": [],
        }
    ]
}

OBJECT_STORAGE_TYPES = {
    "data": [
        {
            "id": "objectstorage",
            "label": "Object Storage",
            "price": {"hourly": 0.0205, "monthly": None},
            "region_prices": [],
        }
    ]
}

LKE_TYPES = {
    "data": [
        {
            "id": "lke-sa",
            "label": "LKE Standard Availability",
            "price": {"hourly": 0.0, "monthly": 0.0},
            "region_prices": [],
        },
        {
            "id": "lke-ha",
            "label": "LKE High Availability",
            "price": {"hourly": 0.09, "monthly": 60.0},
            "region_prices": [{"id": "id-cgk", "hourly": 0.11, "monthly": 72.0}],
        },
        {
            "id": "lke-e",
            "label": "LKE Enterprise",
            "price": {"hourly": 0.45, "monthly": 300.0},
            "region_prices": [],
        },
    ]
}

REGION_AVAILABILITY = {
    "data": [
        {"region": "us-east", "plan": "g6-standard-1", "available": True},
        {"region": "us-east", "plan": "g2-gpu-rtx4000a1-s", "available": False},
    ]
}

REGION_AVAILABILITY_ONE = {
    "data": [
        {"region": "us-east", "plan": "g2-gpu-rtx4000a1-s", "available": True},
    ]
}

_CACHED_GET_MAP = {
    "/regions": REGIONS,
    "/linode/types": LINODE_TYPES,
    "/network-transfer/prices": NETWORK_TRANSFER_PRICES,
    "/object-storage/types": OBJECT_STORAGE_TYPES,
    "/lke/types": LKE_TYPES,
}

_PUBLIC_GET_MAP = {
    "/regions/availability": REGION_AVAILABILITY,
    "/regions/us-east/availability": REGION_AVAILABILITY_ONE,
}


@pytest.fixture
def mock_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the client wrapper's GET methods to serve catalog fixtures."""

    def fake_cached_get(self: Any, path: str, params: Any = None) -> Any:
        if path in _CACHED_GET_MAP:
            return _CACHED_GET_MAP[path]
        raise KeyError(f"unexpected cached_get path: {path}")

    def fake_public_get(self: Any, path: str, params: Any = None) -> Any:
        if path in _PUBLIC_GET_MAP:
            return _PUBLIC_GET_MAP[path]
        if path in _CACHED_GET_MAP:
            return _CACHED_GET_MAP[path]
        raise KeyError(f"unexpected public_get path: {path}")

    monkeypatch.setattr(client_mod.LinodeClientWrapper, "cached_get", fake_cached_get)
    monkeypatch.setattr(client_mod.LinodeClientWrapper, "public_get", fake_public_get)
