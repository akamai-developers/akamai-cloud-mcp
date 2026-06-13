"""Server construction and domain-toggle tests."""

from __future__ import annotations

import pytest
from fastmcp.client import Client

from akamai_cloud_mcp.config import ALL_DOMAINS, parse_domains
from akamai_cloud_mcp.server import build_server


async def _tool_names(mcp) -> set[str]:
    async with Client(mcp) as client:
        return {t.name for t in await client.list_tools()}


def test_build_server_returns_fastmcp() -> None:
    from fastmcp import FastMCP

    assert isinstance(build_server(domains="all"), FastMCP)


def test_parse_domains_all() -> None:
    assert parse_domains("all") == ALL_DOMAINS
    assert parse_domains(None) == ALL_DOMAINS


def test_parse_domains_subset_preserves_order_and_dedups() -> None:
    assert parse_domains("compute,pricing,compute") == ("compute", "pricing")


def test_parse_domains_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        parse_domains("compute,bogus")


async def test_all_domains_construct() -> None:
    # Phase 1: zero tools is acceptable; the server must still construct cleanly.
    mcp = build_server(domains="all")
    names = await _tool_names(mcp)
    assert isinstance(names, set)
