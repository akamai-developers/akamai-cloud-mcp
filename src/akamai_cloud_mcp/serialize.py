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
