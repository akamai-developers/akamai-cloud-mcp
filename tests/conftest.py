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

VOLUME_TYPES = {
    "data": [
        {
            "id": "volume",
            "label": "Storage Volume",
            "price": {"hourly": 0.00015, "monthly": 0.1},
            "region_prices": [],
        }
    ]
}

NODEBALANCER_TYPES = {
    "data": [
        {
            "id": "nodebalancer",
            "label": "NodeBalancer",
            "price": {"hourly": 0.015, "monthly": 10.0},
            "region_prices": [],
        }
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

INSTANCES = {
    "data": [
        {
            "id": 111,
            "label": "web-1",
            "region": "us-east",
            "type": "g6-standard-1",
            "status": "running",
            "ipv4": ["192.0.2.10"],
            "ipv6": "2600:3c03::f03c:1234/64",
            "image": "linode/ubuntu24.04",
            "tags": ["web", "prod"],
            "hypervisor": "kvm",
            "specs": {"vcpus": 1, "memory": 2048, "disk": 51200, "transfer": 2000},
            # Not in the allowlist; must not appear in serialized output.
            "alerts": {"cpu": 90},
        },
        {
            "id": 222,
            "label": "db-1",
            "region": "us-east",
            "type": "g6-standard-4",
            "status": "running",
            "ipv4": ["192.0.2.20"],
            "ipv6": "2600:3c03::f03c:5678/64",
            "image": "linode/debian12",
            "tags": ["db"],
            "hypervisor": "kvm",
            "specs": {"vcpus": 4, "memory": 8192, "disk": 163840, "transfer": 5000},
        },
    ]
}

INSTANCE_ONE = {
    "id": 111,
    "label": "web-1",
    "region": "us-east",
    "type": "g6-standard-1",
    "status": "running",
    "ipv4": ["192.0.2.10"],
    "ipv6": "2600:3c03::f03c:1234/64",
    "image": "linode/ubuntu24.04",
    "tags": ["web", "prod"],
    "hypervisor": "kvm",
    "specs": {"vcpus": 1, "memory": 2048, "disk": 51200, "transfer": 2000},
}

VOLUMES = {
    "data": [
        {
            "id": 9001,
            "label": "data-vol",
            "size": 100,
            "region": "us-east",
            "status": "active",
            "linode_id": 111,
            "linode_label": "web-1",
            "filesystem_path": "/dev/disk/by-id/scsi-0Linode_Volume_data-vol",
            "hardware_type": "nvme",
            "encryption": "enabled",
            "tags": [],
        }
    ]
}

# LKE fixtures. The cluster carries a planted kubeconfig that must NEVER survive.
_FAKE_KUBECONFIG_B64 = "YXBpVmVyc2lvbjogdjEKa2luZDogQ29uZmlnCg=="

LKE_CLUSTERS = {
    "data": [
        {
            "id": 555,
            "label": "prod-cluster",
            "region": "us-east",
            "k8s_version": "1.31",
            "tier": "standard",
            "control_plane": {"high_availability": True},
            "tags": ["prod"],
            # Planted secret: a list endpoint must not surface this.
            "kubeconfig": _FAKE_KUBECONFIG_B64,
        }
    ]
}

LKE_CLUSTER_ONE = {
    "id": 555,
    "label": "prod-cluster",
    "region": "us-east",
    "k8s_version": "1.31",
    "tier": "standard",
    "control_plane": {"high_availability": True},
    "tags": ["prod"],
    "kubeconfig": _FAKE_KUBECONFIG_B64,
}

LKE_POOLS = {
    "data": [
        {
            "id": 700,
            "type": "g6-standard-4",
            "count": 3,
            "autoscaler": {"enabled": True, "min": 3, "max": 6},
            "nodes": [
                {"id": "node-1", "instance_id": 901, "status": "ready"},
                {"id": "node-2", "instance_id": 902, "status": "ready"},
            ],
            "tags": [],
        }
    ]
}

LKE_API_ENDPOINTS = {"data": [{"endpoint": "https://555.us-east.linodelke.net:443"}]}
LKE_ACL = {"acl": {"enabled": True, "addresses": {"ipv4": ["203.0.113.0/24"]}}}
LKE_DASHBOARD = {"url": "https://555.us-east.linodelke.net/dashboard"}
LKE_VERSIONS = {"data": [{"id": "1.31"}, {"id": "1.30"}]}

# Object Storage fixtures. Buckets carry planted key material that must not leak.
_FAKE_ACCESS_KEY = "AKFAKE1234567890OBJ"
_FAKE_SECRET_KEY = "abcdEFGH1234567890secretkeymaterialxyz99"

OBJ_BUCKETS = {
    "data": [
        {
            "label": "assets",
            "region": "us-east",
            "cluster": "us-east-1",
            "hostname": "assets.us-east-1.linodeobjects.com",
            "s3_endpoint": "us-east-1.linodeobjects.com",
            "endpoint_type": "E1",
            "created": "2026-01-01T00:00:00",
            "size": 10485760,
            "objects": 42,
            # Planted secrets: must never appear in output.
            "access_key": _FAKE_ACCESS_KEY,
            "secret_key": _FAKE_SECRET_KEY,
        }
    ]
}

OBJ_ENDPOINTS = {
    "data": [
        {"region": "us-east", "endpoint_type": "E1", "s3_endpoint": "us-east-1.linodeobjects.com"}
    ]
}

OBJ_TRANSFER = {"used": 123456789, "quota": 1099511627776, "billable": 0}

OBJ_QUOTAS = {
    "data": [
        {
            "quota_id": "obj-buckets-us-east",
            "quota_name": "Number of buckets",
            "endpoint_type": "E1",
            "s3_endpoint": "us-east-1.linodeobjects.com",
            "quota_limit": 1000,
            "resource_metric": "bucket",
        }
    ]
}

FIREWALLS = {
    "data": [
        {
            "id": 1,
            "label": "web-fw",
            "status": "enabled",
            "rules": {"inbound_policy": "DROP", "outbound_policy": "ACCEPT", "inbound": []},
            "tags": [],
        }
    ]
}

IPS = {
    "data": [
        {
            "address": "192.0.2.10",
            "type": "ipv4",
            "public": True,
            "rdns": "li-1.members.linode.com",
            "region": "us-east",
            "linode_id": 111,
        }
    ]
}

VLANS = {
    "data": [{"label": "dev-vlan", "region": "us-east", "cidr": "10.0.0.0/24", "linodes": [111]}]
}

VPCS = {
    "data": [
        {
            "id": 30,
            "label": "prod-vpc",
            "description": "Production VPC",
            "region": "us-east",
        }
    ]
}

VPC_ONE = {
    "id": 30,
    "label": "prod-vpc",
    "description": "Production VPC",
    "region": "us-east",
    "subnets": [
        {"id": 300, "label": "web", "ipv4": "10.0.1.0/24", "linodes": [{"id": 111}]},
        {"id": 301, "label": "db", "ipv4": "10.0.2.0/24", "linodes": []},
    ],
}

NODEBALANCERS = {
    "data": [
        {
            "id": 77,
            "label": "lb-1",
            "region": "us-east",
            "hostname": "nb-192-0-2-30.newark.nodebalancer.linode.com",
            "ipv4": "192.0.2.30",
            "ipv6": "2600:3c03::1",
            "client_conn_throttle": 0,
            "tags": [],
            "transfer": {"in": 1.5, "out": 2.5, "total": 4.0},
        }
    ]
}

# Account fixtures. PII and payment fields are planted and must be redacted.
_FAKE_EMAIL = "owner@example.com"
_FAKE_PHONE = "+1-555-0100"
_FAKE_CARD = "4111111111111111"

ACCOUNT = {
    "company": "Example Co",
    "country": "US",
    "balance": 0.0,
    "balance_uninvoiced": 12.5,
    "active_since": "2020-01-01T00:00:00",
    "capabilities": ["Linodes", "Object Storage", "Kubernetes"],
    "billing_source": "linode",
    "euuid": "AAAAAAAA-BBBB-CCCC-DDDDDDDDDDDD",
    # Planted PII / payment: must not survive.
    "first_name": "Pat",
    "last_name": "Doe",
    "email": _FAKE_EMAIL,
    "phone": _FAKE_PHONE,
    "address_1": "123 Main St",
    "city": "Philadelphia",
    "state": "PA",
    "zip": "19103",
    "tax_id": "12-3456789",
    "credit_card": {"last_four": "1111", "expiry": "12/2030", "number": _FAKE_CARD},
}

ACCOUNT_TRANSFER = {
    "used": 500,
    "quota": 1024,
    "billable": 0,
    "region_transfers": [{"id": "us-east", "used": 300, "quota": 1024, "billable": 0}],
}

INVOICES = {
    "data": [
        {
            "id": 1001,
            "label": "Invoice #1001",
            "date": "2026-05-01T00:00:00",
            "subtotal": 100.0,
            "tax": 6.0,
            "total": 106.0,
            "status": "paid",
            # Planted payment detail that should be scrubbed if present.
            "payment_method": {"card_number": _FAKE_CARD},
        }
    ]
}

EVENTS = {
    "data": [
        {
            "id": 9,
            "action": "linode_boot",
            "created": "2026-06-01T00:00:00",
            "entity": {
                "id": 111,
                "label": "web-1",
                "type": "linode",
                "url": "/v4/linode/instances/111",
            },
            "username": "patdoe",
            "status": "finished",
            "seen": True,
            "read": True,
            "percent_complete": 100,
        }
    ]
}

_GET_MAP = {
    "/linode/instances": INSTANCES,
    "/linode/instances/111": INSTANCE_ONE,
    "/volumes": VOLUMES,
    "/account": ACCOUNT,
    "/account/transfer": ACCOUNT_TRANSFER,
    "/account/invoices": INVOICES,
    "/account/events": EVENTS,
    "/networking/firewalls": FIREWALLS,
    "/networking/ips": IPS,
    "/networking/vlans": VLANS,
    "/vpcs": VPCS,
    "/vpcs/30": VPC_ONE,
    "/nodebalancers": NODEBALANCERS,
    "/object-storage/buckets": OBJ_BUCKETS,
    "/object-storage/endpoints": OBJ_ENDPOINTS,
    "/object-storage/transfer": OBJ_TRANSFER,
    "/object-storage/quotas": OBJ_QUOTAS,
    "/lke/clusters": LKE_CLUSTERS,
    "/lke/clusters/555": LKE_CLUSTER_ONE,
    "/lke/clusters/555/pools": LKE_POOLS,
    "/lke/clusters/555/api-endpoints": LKE_API_ENDPOINTS,
    "/lke/clusters/555/control_plane_acl": LKE_ACL,
    "/lke/clusters/555/dashboard": LKE_DASHBOARD,
    "/lke/versions": LKE_VERSIONS,
}

_CACHED_GET_MAP = {
    "/regions": REGIONS,
    "/linode/types": LINODE_TYPES,
    "/network-transfer/prices": NETWORK_TRANSFER_PRICES,
    "/object-storage/types": OBJECT_STORAGE_TYPES,
    "/lke/types": LKE_TYPES,
    "/volumes/types": VOLUME_TYPES,
    "/nodebalancers/types": NODEBALANCER_TYPES,
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


@pytest.fixture
def mock_get(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the client wrapper's raw GET to serve account fixtures by path."""

    def fake_get(self: Any, path: str, params: Any = None) -> Any:
        if path in _GET_MAP:
            return _GET_MAP[path]
        raise KeyError(f"unexpected get path: {path}")

    monkeypatch.setattr(client_mod.LinodeClientWrapper, "get", fake_get)
