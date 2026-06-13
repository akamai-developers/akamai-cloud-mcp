"""Loader for the in-repo curated price reference.

Some cost categories are invisible to the Linode API (Object Storage request
pricing, free-allotment thresholds, policy facts). They live in
`data/pricing_supplement.json`, each entry carrying a `source` and a
`last_reviewed` date. The marketing and techdocs pages are human update sources
only; nothing here is scraped at runtime.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache(maxsize=1)
def load_supplement() -> dict[str, Any]:
    """Return the parsed pricing supplement, cached for the process lifetime."""
    data_file = resources.files("akamai_cloud_mcp.data").joinpath("pricing_supplement.json")
    with data_file.open("r", encoding="utf-8") as handle:
        result: dict[str, Any] = json.load(handle)
    return result


def object_storage_request_pricing() -> dict[str, Any]:
    return load_supplement()["object_storage_requests"]


def object_storage_allotments() -> dict[str, Any]:
    return load_supplement()["object_storage_allotments"]


def transfer_pool() -> dict[str, Any]:
    pool: dict[str, Any] = load_supplement()["transfer_pool"]
    return pool


def policy_facts() -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = load_supplement().get("policy_facts", [])
    return facts
