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

# Lean by default for model consumption: resolvers (DNS IPs) and
# placement_group_limits are noise a model never reasons about. Full detail is
# available through the escape hatch (linode_api_get /regions).
REGION_FIELDS = [
    "id",
    "label",
    "country",
    "capabilities",
    "status",
    "site_type",
]

# Type/plan fields. "class" is the API key (the SDK renames it to type_class);
# raw GET dicts carry "class" directly, so we read both.
# Lean set for catalog listing. disk/transfer/network_out/addons/successor are
# dropped from the listing to keep it digestible; estimate_cost reads addons and
# the full price object from the raw types endpoint, not from this serializer.
TYPE_FIELDS = [
    "id",
    "label",
    "class",
    "vcpus",
    "memory",
    "gpus",
    "accelerated_devices",
    "price",
    "region_prices",
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
    "tags",
]


def serialize_instance(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize a compute instance (SDK object or raw dict)."""
    return pick(obj, INSTANCE_FIELDS)


def serialize_volume(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize a block storage volume (SDK object or raw dict)."""
    return pick(obj, VOLUME_FIELDS)


# -- Account & billing allowlists ----------------------------------------
# These DELIBERATELY exclude PII and payment fields: no first_name, last_name,
# email, phone, address_1/2, city, state, zip, tax_id, or credit_card. scrub()
# is the backstop on top of this allowlist.
ACCOUNT_FIELDS = [
    "company",
    "country",
    "balance",
    "balance_uninvoiced",
    "active_since",
    "capabilities",
    "active_promotions",
    "billing_source",
    "euuid",
]
INVOICE_FIELDS = ["id", "label", "date", "subtotal", "tax", "total", "status", "tax_summary"]
EVENT_FIELDS = [
    "id",
    "action",
    "created",
    "entity",
    "username",
    "status",
    "percent_complete",
]


def serialize_account(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize the account, excluding PII and payment fields."""
    return pick(obj, ACCOUNT_FIELDS)


def serialize_invoice(obj: Any) -> dict[str, Any]:
    return pick(obj, INVOICE_FIELDS)


def serialize_event(obj: Any) -> dict[str, Any]:
    return pick(obj, EVENT_FIELDS)


# -- Networking allowlists -----------------------------------------------

# rules and entities are dropped from the listing (rule sets are large); fetch a
# single firewall's rules through the escape hatch when needed.
FIREWALL_FIELDS = ["id", "label", "status", "tags", "created", "updated"]
IP_FIELDS = [
    "address",
    "type",
    "public",
    "rdns",
    "region",
    "linode_id",
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


# Firewall detail allowlists. The list view (serialize_firewall) deliberately
# drops rules and entities; get_firewall surfaces them. No secrets in the schema.
FIREWALL_RULE_FIELDS = ["action", "protocol", "ports", "addresses", "label", "description"]
FIREWALL_ENTITY_FIELDS = ["id", "label", "type", "url", "parent_entity"]
FIREWALL_DETAIL_FIELDS = ["id", "label", "status", "tags", "created", "updated"]


def serialize_firewall_rule(obj: Any) -> dict[str, Any]:
    return pick(obj, FIREWALL_RULE_FIELDS)


def serialize_firewall_detail(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize one firewall with its inbound/outbound rules and the
    entities it is attached to. The raw GET carries rules/entities inline, so no
    lazy SDK fetch is triggered."""
    result = pick(obj, FIREWALL_DETAIL_FIELDS)
    rules_raw = obj.get("rules") if isinstance(obj, dict) else getattr(obj, "rules", None)
    rules = rules_raw if isinstance(rules_raw, dict) else {}
    result["rules"] = {
        "inbound_policy": rules.get("inbound_policy"),
        "outbound_policy": rules.get("outbound_policy"),
        "inbound": [serialize_firewall_rule(r) for r in (rules.get("inbound") or [])],
        "outbound": [serialize_firewall_rule(r) for r in (rules.get("outbound") or [])],
        "version": rules.get("version"),
        "fingerprint": rules.get("fingerprint"),
    }
    entities_raw = obj.get("entities") if isinstance(obj, dict) else getattr(obj, "entities", None)
    result["entities"] = [pick(e, FIREWALL_ENTITY_FIELDS) for e in (entities_raw or [])]
    return result


# DNS (Domains) allowlists. No secret material. soa_email is the public zone SOA
# contact, not account PII: scrub redacts the exact key "email", not "soa_email".
DOMAIN_FIELDS = [
    "id",
    "domain",
    "type",
    "status",
    "description",
    "soa_email",
    "group",
    "tags",
    "ttl_sec",
    "refresh_sec",
    "retry_sec",
    "expire_sec",
    "master_ips",
    "axfr_ips",
]
DOMAIN_RECORD_FIELDS = [
    "id",
    "type",
    "name",
    "target",
    "priority",
    "weight",
    "port",
    "service",
    "protocol",
    "ttl_sec",
    "tag",
    "created",
    "updated",
]


def serialize_domain(obj: Any) -> dict[str, Any]:
    return pick(obj, DOMAIN_FIELDS)


def serialize_domain_record(obj: Any) -> dict[str, Any]:
    return pick(obj, DOMAIN_RECORD_FIELDS)


# Managed Databases allowlists. Connection credentials (root_username/
# root_password) and the CA cert live on separate /credentials and /ssl
# subendpoints that are denylisted in the escape hatch; they are never named here.
DATABASE_INSTANCE_FIELDS = [
    "id",
    "label",
    "engine",
    "version",
    "region",
    "status",
    "type",
    "cluster_size",
    "hosts",
    "port",
    "ssl_connection",
    "encrypted",
    "allow_list",
    "platform",
    "fork",
    "oldest_restore_time",
    "updates",
    "created",
    "updated",
    "instance_uri",
]
DATABASE_ENGINE_FIELDS = ["id", "engine", "version"]
DATABASE_TYPE_FIELDS = [
    "id",
    "label",
    "class",
    "vcpus",
    "memory",
    "disk",
    "engines",
    "price",
    "region_prices",
    "deprecated",
]


def serialize_database(obj: Any) -> dict[str, Any]:
    return pick(obj, DATABASE_INSTANCE_FIELDS)


def serialize_database_engine(obj: Any) -> dict[str, Any]:
    return pick(obj, DATABASE_ENGINE_FIELDS)


def serialize_database_type(obj: Any) -> dict[str, Any]:
    """Allowlist-serialize a database plan type. Backfills the API "class" from
    the SDK's "type_class", like serialize_type."""
    result = pick(obj, DATABASE_TYPE_FIELDS)
    if result.get("class") is None:
        type_class = _get(obj, "type_class")
        if type_class is not None:
            result["class"] = _normalize(type_class)
    return result


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
