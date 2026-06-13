"""Managed Databases tools: list/get, engine validation, credential safety."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastmcp.client import Client
from fastmcp.exceptions import ToolError

from akamai_cloud_mcp.server import build_server
from tests.conftest import _FAKE_DB_PASSWORD


async def _call(mcp: Any, name: str, args: dict[str, Any] | None = None) -> Any:
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
        return result.data


async def _tool_names(mcp: Any) -> set[str]:
    async with Client(mcp) as client:
        return {t.name for t in await client.list_tools()}


async def test_database_tools_register() -> None:
    names = await _tool_names(build_server(domains="databases"))
    assert {
        "linode_list_databases",
        "linode_get_database",
        "linode_list_database_engines",
        "linode_list_database_types",
    } <= names


async def test_list_databases_drops_credentials(mock_get: None) -> None:
    data = await _call(build_server(domains="databases"), "linode_list_databases")
    assert data["count"] == 1
    db = data["databases"][0]
    assert db["engine"] == "mysql"
    assert db["hosts"]["primary"].endswith("linodedb.net")
    # Planted credentials must never survive the allowlist serializer.
    assert "root_password" not in db
    assert "root_username" not in db
    assert _FAKE_DB_PASSWORD not in json.dumps(data)


async def test_get_database_routes_by_engine(mock_get: None) -> None:
    data = await _call(
        build_server(domains="databases"),
        "linode_get_database",
        {"engine": "mysql", "database_id": 55},
    )
    assert data["database"]["id"] == 55
    assert _FAKE_DB_PASSWORD not in json.dumps(data)


async def test_get_database_rejects_unknown_engine(mock_get: None) -> None:
    # Engine validation also blocks path injection into /databases/{engine}/...
    with pytest.raises(ToolError):
        await _call(
            build_server(domains="databases"),
            "linode_get_database",
            {"engine": "redis", "database_id": 55},
        )


async def test_list_database_engines_and_types(mock_get: None) -> None:
    engines = await _call(build_server(domains="databases"), "linode_list_database_engines")
    assert {e["engine"] for e in engines["engines"]} == {"mysql", "postgresql"}
    types = await _call(build_server(domains="databases"), "linode_list_database_types")
    assert types["types"][0]["class"] == "dedicated"
