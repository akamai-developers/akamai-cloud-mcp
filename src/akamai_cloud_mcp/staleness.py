"""Pricing staleness diff.

Compares current type/price data against a known baseline and reports what
changed. Two honest modes:

- In the normal test suite this runs against MOCK data, so it only exercises the
  diff CODE PATH. It cannot catch real catalog drift, because the mock is what we
  wrote.
- A separate scheduled CI job that fetches the LIVE public type endpoints is the
  only thing that catches real drift. See the CI workflow.
"""

from __future__ import annotations

from typing import Any


def diff_prices(
    current: list[dict[str, Any]], baseline: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return a list of changes between current type rows and a baseline.

    baseline maps a type id to its expected {"hourly", "monthly"}. Reports
    removed ids, added ids, and changed default prices.
    """
    changes: list[dict[str, Any]] = []
    current_by_id = {e["id"]: e for e in current if isinstance(e, dict) and "id" in e}

    for type_id, expected in baseline.items():
        entry = current_by_id.get(type_id)
        if entry is None:
            changes.append({"id": type_id, "change": "removed"})
            continue
        price = entry.get("price") or {}
        now = {"hourly": price.get("hourly"), "monthly": price.get("monthly")}
        if now != {"hourly": expected.get("hourly"), "monthly": expected.get("monthly")}:
            changes.append({"id": type_id, "change": "price_changed", "was": expected, "now": now})

    for type_id in current_by_id:
        if type_id not in baseline:
            changes.append({"id": type_id, "change": "added"})

    return changes
