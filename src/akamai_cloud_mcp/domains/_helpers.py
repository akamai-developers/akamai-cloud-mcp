"""Small shared helpers for domain modules."""

from __future__ import annotations

from typing import Any

# Read-only annotation applied to every tool.
READ_ONLY = {"readOnlyHint": True}


def data_list(resp: Any) -> list[Any]:
    """Extract the row list from a paged response, a bare list, or a single dict."""
    if isinstance(resp, dict) and "data" in resp:
        data = resp["data"]
        return data if isinstance(data, list) else [data]
    if isinstance(resp, list):
        return resp
    return [resp]


def cap(rows: list[Any], max_results: int) -> tuple[list[Any], bool]:
    """Truncate rows to max_results, returning (rows, was_capped)."""
    if len(rows) > max_results:
        return rows[:max_results], True
    return rows, False
