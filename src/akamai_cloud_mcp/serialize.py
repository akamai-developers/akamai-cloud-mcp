"""Allowlist serializers: the PRIMARY defense against leaking secrets.

`linode_api4` models are lazy: accessing an attribute (for example
`LKECluster.kubeconfig`) can trigger a network fetch and return secret material.
So we never call `vars(obj)` or a blanket model dump. Each serializer copies ONLY
named safe fields out of the SDK object into a plain dict. Secret-bearing
attributes are simply never read.

`scrub()` still runs on top of every serialized result as a backstop.
"""

from __future__ import annotations

from typing import Any


def _get(obj: Any, name: str) -> Any:
    """Safely read one attribute (or dict key) without raising on absence.

    Wrapped in try/except because SDK lazy attributes can raise on fetch; a
    missing or unfetchable field becomes None rather than an error or a leak.
    """
    try:
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)
    except Exception:
        return None


def pick(obj: Any, fields: list[str]) -> dict[str, Any]:
    """Copy only the named fields out of an SDK object into a plain dict."""
    return {name: _normalize(_get(obj, name)) for name in fields}


# -- Per-resource allowlists ---------------------------------------------

REGION_FIELDS = [
    "id",
    "label",
    "country",
    "capabilities",
    "status",
    "site_type",
    "resolvers",
    "placement_group_limits",
]

# Type/plan fields. "class" is the API key (the SDK renames it to type_class);
# raw GET dicts carry "class" directly, so we read both.
TYPE_FIELDS = [
    "id",
    "label",
    "class",
    "vcpus",
    "memory",
    "disk",
    "transfer",
    "network_out",
    "gpus",
    "accelerated_devices",
    "price",
    "region_prices",
    "addons",
    "successor",
]


def serialize_region(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize a region (SDK object or raw dict)."""
    return pick(obj, REGION_FIELDS)


INSTANCE_FIELDS = [
    "id",
    "label",
    "region",
    "type",
    "status",
    "ipv4",
    "ipv6",
    "image",
    "group",
    "tags",
    "hypervisor",
    "specs",
    "watchdog_enabled",
    "site_type",
    "created",
    "updated",
]

VOLUME_FIELDS = [
    "id",
    "label",
    "size",
    "region",
    "status",
    "linode_id",
    "linode_label",
    "filesystem_path",
    "hardware_type",
    "encryption",
    "tags",
    "created",
    "updated",
]


def serialize_instance(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize a compute instance (SDK object or raw dict)."""
    return pick(obj, INSTANCE_FIELDS)


def serialize_volume(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize a block storage volume (SDK object or raw dict)."""
    return pick(obj, VOLUME_FIELDS)


# -- Networking allowlists -----------------------------------------------

FIREWALL_FIELDS = ["id", "label", "status", "rules", "tags", "entities", "created", "updated"]
IP_FIELDS = [
    "address",
    "type",
    "public",
    "rdns",
    "region",
    "linode_id",
    "gateway",
    "subnet_mask",
    "prefix",
    "vpc_nat_1_1",
]
VLAN_FIELDS = ["label", "region", "cidr", "linodes", "created"]
VPC_FIELDS = ["id", "label", "description", "region", "created", "updated"]
SUBNET_FIELDS = ["id", "label", "ipv4", "linodes", "created", "updated"]
NODEBALANCER_FIELDS = [
    "id",
    "label",
    "region",
    "hostname",
    "ipv4",
    "ipv6",
    "client_conn_throttle",
    "tags",
    "transfer",
    "created",
    "updated",
]


def serialize_firewall(obj: Any) -> dict[str, Any]:
    return pick(obj, FIREWALL_FIELDS)


def serialize_ip(obj: Any) -> dict[str, Any]:
    return pick(obj, IP_FIELDS)


def serialize_vlan(obj: Any) -> dict[str, Any]:
    return pick(obj, VLAN_FIELDS)


def serialize_vpc(obj: Any) -> dict[str, Any]:
    return pick(obj, VPC_FIELDS)


def serialize_subnet(obj: Any) -> dict[str, Any]:
    return pick(obj, SUBNET_FIELDS)


def serialize_nodebalancer(obj: Any) -> dict[str, Any]:
    return pick(obj, NODEBALANCER_FIELDS)


# Object Storage bucket allowlist. No access/secret key fields, ever.
OBJECT_STORAGE_BUCKET_FIELDS = [
    "label",
    "region",
    "cluster",
    "hostname",
    "s3_endpoint",
    "endpoint_type",
    "created",
    "size",
    "objects",
]


def serialize_bucket(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize an Object Storage bucket. Never includes key material."""
    return pick(obj, OBJECT_STORAGE_BUCKET_FIELDS)


# LKE cluster allowlist. kubeconfig is DELIBERATELY absent and must never be added.
LKE_CLUSTER_FIELDS = [
    "id",
    "label",
    "region",
    "k8s_version",
    "tier",
    "control_plane",
    "apl_enabled",
    "tags",
    "created",
    "updated",
]

LKE_POOL_FIELDS = [
    "id",
    "type",
    "count",
    "autoscaler",
    "nodes",
    "disks",
    "disk_encryption",
    "labels",
    "taints",
    "tags",
    "k8s_version",
    "update_strategy",
]


def serialize_lke_cluster(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize an LKE cluster. Never reads or returns kubeconfig."""
    return pick(obj, LKE_CLUSTER_FIELDS)


def serialize_lke_pool(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize an LKE node pool."""
    return pick(obj, LKE_POOL_FIELDS)


def serialize_type(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize an instance/plan type (SDK object or raw dict)."""
    result = pick(obj, TYPE_FIELDS)
    # SDK objects expose the class as `type_class`; backfill when "class" missing.
    if result.get("class") is None:
        type_class = _get(obj, "type_class")
        if type_class is not None:
            result["class"] = _normalize(type_class)
    return result


def _normalize(value: Any) -> Any:
    """Coerce SDK value objects into JSON-safe primitives.

    Nested SDK models keep their `.id` (the safe handle) rather than being
    serialized whole, which would risk pulling secret lazy attributes.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize(v) for v in value]
    # SDK enum-like / value objects: prefer a string value if present.
    for attr in ("value", "label", "id"):
        if hasattr(value, attr):
            return _normalize(getattr(value, attr))
    return str(value)
