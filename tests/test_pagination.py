"""Pagination: list_* tools must fetch every page, not silently stop at page 1.

Regression for the bug where the curated inventory tools read only the first
~100 rows yet reported the list as complete (capped=false).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp.client import Client

from akamai_cloud_mcp.client import LinodeClientWrapper
from akamai_cloud_mcp.config import Config
from akamai_cloud_mcp.server import build_server


def _paged_get(pages: dict[int, list[Any]], total_pages: int) -> Any:
    """Return a fake wrapper.get that serves a paginated envelope by page param."""

    def fake_get(self: Any, path: str, params: Any = None) -> Any:
        page = int(params.get("page", 1)) if isinstance(params, dict) else 1
        return {
            "data": pages.get(page, []),
            "page": page,
            "pages": total_pages,
            "results": sum(len(v) for v in pages.values()),
        }

    return fake_get


def test_get_all_fetches_every_page(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = {
        1: [{"id": i} for i in range(100)],
        2: [{"id": i} for i in range(100, 150)],
    }
    monkeypatch.setattr(LinodeClientWrapper, "get", _paged_get(pages, total_pages=2))
    wrapper = LinodeClientWrapper(Config(), token="x")
    rows = wrapper.get_all("/linode/instances")
    assert len(rows) == 150
    assert rows[-1]["id"] == 149


async def test_list_tool_reports_capped_across_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    # 150 instances across two pages, capped at 50: the tool must read both pages
    # and honestly report capped=true rather than claiming the first page is all.
    pages = {
        1: [{"id": i, "label": f"i{i}", "region": "us-east"} for i in range(100)],
        2: [{"id": i, "label": f"i{i}", "region": "us-east"} for i in range(100, 150)],
    }
    monkeypatch.setattr(LinodeClientWrapper, "get", _paged_get(pages, total_pages=2))
    config = Config(max_results=50)
    async with Client(build_server(domains="compute", config=config)) as client:
        result = await client.call_tool("linode_list_instances", {})
    data = result.data
    assert data["count"] == 50
    assert data["capped"] is True
