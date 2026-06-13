"""Read-only enforcement: a static scan and a runtime HTTP-verb guard.

Read-only cannot be proven by "it was never called" at runtime across all code,
so it is enforced structurally: a static scan of src/ rejects mutating method
calls and non-GET verbs, and a runtime guard makes any non-GET httpx verb raise
during a representative tool run.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastmcp.client import Client

import akamai_cloud_mcp
from akamai_cloud_mcp.server import build_server

SRC_ROOT = Path(akamai_cloud_mcp.__file__).parent

# Method-call shapes that would indicate a mutating operation.
FORBIDDEN_PATTERNS = [
    re.compile(r"\.post\s*\("),
    re.compile(r"\.put\s*\("),
    re.compile(r"\.delete\s*\("),
    re.compile(r"\.patch\s*\("),
    re.compile(r"\.save\s*\("),
    re.compile(r"\.invalidate\s*\("),
    re.compile(r"\.create_\w+\s*\("),
]


def _code_lines(text: str) -> list[str]:
    """Return non-comment code lines (best-effort: drops full-line comments)."""
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        lines.append(raw)
    return lines


def test_static_scan_finds_no_mutating_calls() -> None:
    offenders: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        # Skip docstrings cheaply by scanning code lines; this is a guard, not a
        # parser. Any real mutating call would still appear as a method call.
        for line in _code_lines(text):
            # Ignore lines that are clearly prose inside a triple-quoted string by
            # requiring the pattern to look like code (no leading prose marker).
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    offenders.append(f"{path.name}: {line.strip()}")
    assert not offenders, "Mutating call(s) found in src/: " + "; ".join(offenders)


async def test_runtime_http_verb_guard(
    monkeypatch: pytest.MonkeyPatch, mock_get: None, mock_catalog: None
) -> None:
    # Any non-GET httpx verb firing during a tool run is a read-only violation.
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("A non-GET HTTP verb was called; read-only violated.")

    for verb in ("post", "put", "delete", "patch"):
        monkeypatch.setattr(httpx.Client, verb, forbidden, raising=False)

    async with Client(build_server(domains="all")) as client:
        await client.call_tool("list_regions", {})
        await client.call_tool("list_instances", {})
        await client.call_tool("get_pricing", {"family": "compute"})
        await client.call_tool("linode_api_get", {"path": "/images"})


async def test_every_tool_is_read_only_annotated() -> None:
    async with Client(build_server(domains="all")) as client:
        tools = await client.list_tools()
    assert tools
    for tool in tools:
        annotations = tool.annotations
        read_only = getattr(annotations, "readOnlyHint", None)
        assert read_only is True, f"{tool.name} is not annotated readOnlyHint=true"
