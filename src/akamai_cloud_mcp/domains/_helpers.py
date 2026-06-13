"""Small shared helpers for domain modules."""

from __future__ import annotations

from typing import Any, Literal

# Read-only annotation applied to every tool.
READ_ONLY = {"readOnlyHint": True}

# Per-call response verbosity (Anthropic: let the caller control detail). "full"
# returns the whole serialized row; "concise" keeps only identity/routing fields
# so a long list stays cheap and the agent can drill into one resource after.
Detail = Literal["concise", "full"]

CONCISE_KEYS = frozenset(
    {
        "id",
        "label",
        "name",
        "domain",
        "address",
        "region",
        "status",
        "type",
        "engine",
        "version",
        "k8s_version",
        "tier",
        "hostname",
        "target",
        "size",
        "linode_id",
        "date",
        "total",
        "action",
        "created",
    }
)


def project(row: Any, detail: Detail) -> Any:
    """For detail='concise', keep only identity/routing keys on a serialized row;
    'full' returns it unchanged."""
    if detail == "concise" and isinstance(row, dict):
        return {k: v for k, v in row.items() if k in CONCISE_KEYS}
    return row


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
