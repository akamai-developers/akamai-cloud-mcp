"""Phase 8: escape hatch (linode_api_get) validation, denylist, and scrubbing."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastmcp.client import Client
from fastmcp.exceptions import ToolError as ClientToolError

from akamai_cloud_mcp import client as client_mod
from akamai_cloud_mcp.domains.escape_hatch import is_denied, normalize_path
from akamai_cloud_mcp.errors import ToolError
from akamai_cloud_mcp.server import build_server
from tests.conftest import _FAKE_CARD, _FAKE_EMAIL, _FAKE_PHONE


async def _call(mcp: Any, name: str, args: dict[str, Any] | None = None) -> Any:
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
        return result.data


# -- unit-level path validation ------------------------------------------


def test_normalize_path_adds_leading_slash() -> None:
    assert normalize_path("regions") == "/regions"


def test_normalize_path_strips_v4_prefix() -> None:
    assert normalize_path("/v4/regions") == "/regions"


def test_normalize_path_rejects_absolute_url() -> None:
    with pytest.raises(ToolError):
        normalize_path("https://evil.example.com/regions")


def test_normalize_path_rejects_protocol_relative() -> None:
    with pytest.raises(ToolError):
        normalize_path("//evil.example.com/regions")


def test_normalize_path_rejects_traversal() -> None:
    with pytest.raises(ToolError):
        normalize_path("/regions/../../etc/passwd")


def test_normalize_path_rejects_empty() -> None:
    with pytest.raises(ToolError):
        normalize_path("   ")


def test_denylist_matches() -> None:
    assert is_denied("/lke/clusters/555/kubeconfig")
    assert is_denied("/object-storage/keys")
    assert is_denied("/object-storage/keys/9")
    assert is_denied("/profile/tokens")
    assert is_denied("/account/payment-methods")
    # Managed Database connection credentials and CA cert are denylisted.
    assert is_denied("/databases/mysql/instances/55/credentials")
    assert is_denied("/databases/postgresql/instances/9/credentials")
    assert is_denied("/databases/mysql/instances/55/ssl")
    assert not is_denied("/databases/instances")
    assert not is_denied("/databases/mysql/instances/55")
    assert not is_denied("/regions")
    assert not is_denied("/images")


def test_normalize_path_rejects_encoded_traversal() -> None:
    # Percent-encoded "../" must be decoded and rejected, not passed through to
    # the wire where urllib3 would collapse it onto a denied secret endpoint.
    with pytest.raises(ToolError):
        normalize_path("/regions/%2e%2e/profile/tokens")
    with pytest.raises(ToolError):
        normalize_path("/a/%252e%252e/object-storage/keys")  # double-encoded


def test_denylist_catches_encoded_and_double_slash_bypasses() -> None:
    # Encoded hyphen, encoded slash, doubled slashes, and a /v4 prefix must all
    # normalize to the canonical secret path so the denylist still trips.
    assert is_denied(normalize_path("/account/payment%2dmethods"))
    assert is_denied(normalize_path("/object-storage%2fkeys"))
    assert is_denied(normalize_path("/object-storage//keys"))
    assert is_denied(normalize_path("/v4/profile/tokens"))


# -- tool-level behavior --------------------------------------------------


async def test_escape_hatch_registers() -> None:
    async with Client(build_server(domains="escape")) as client:
        names = {t.name for t in await client.list_tools()}
    assert "linode_api_get" in names


async def test_escape_hatch_normal_get(mock_get: None) -> None:
    data = await _call(build_server(domains="escape"), "linode_api_get", {"path": "/images"})
    assert data["data"][0]["id"] == "linode/ubuntu24.04"


async def test_escape_hatch_scrubs_secret_value(mock_get: None) -> None:
    data = await _call(build_server(domains="escape"), "linode_api_get", {"path": "/leaky"})
    assert data["note"] == "ok"
    assert "BEGIN PRIVATE KEY" not in json.dumps(data)


async def test_escape_hatch_rejects_absolute_url(mock_get: None) -> None:
    with pytest.raises(ClientToolError):
        await _call(
            build_server(domains="escape"),
            "linode_api_get",
            {"path": "https://evil.example.com/x"},
        )


async def test_escape_hatch_rejects_denylisted_path(mock_get: None) -> None:
    with pytest.raises(ClientToolError):
        await _call(
            build_server(domains="escape"),
            "linode_api_get",
            {"path": "/lke/clusters/555/kubeconfig"},
        )


async def test_escape_hatch_rejects_encoded_denylist_bypass(mock_get: None) -> None:
    # A percent-encoded path that decodes onto a denied secret endpoint must be
    # refused, not fetched. Regression for the denylist URL-decode bypass.
    with pytest.raises(ClientToolError):
        await _call(
            build_server(domains="escape"),
            "linode_api_get",
            {"path": "/account/payment%2dmethods"},
        )


async def test_escape_hatch_account_scrubs_pii(mock_get: None) -> None:
    # /account is reachable (not a secret endpoint), but a raw read must not hand
    # the model account-holder PII or card data.
    data = await _call(build_server(domains="escape"), "linode_api_get", {"path": "/account"})
    assert data["company"] == "Example Co"
    blob = json.dumps(data)
    for leaked in (_FAKE_EMAIL, _FAKE_PHONE, _FAKE_CARD, "Pat", "Doe", "123 Main St", "19103"):
        assert leaked not in blob


class _FakeRateLimit(Exception):
    status_code = 429

    class response:  # noqa: N801 - mimics an httpx response attribute
        headers = {"Retry-After": "30"}


async def test_escape_hatch_maps_429(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(self: Any, path: str, params: Any = None) -> Any:
        raise _FakeRateLimit("rate limited")

    monkeypatch.setattr(client_mod.LinodeClientWrapper, "get", boom)
    with pytest.raises(ClientToolError) as excinfo:
        await _call(build_server(domains="escape"), "linode_api_get", {"path": "/images"})
    assert "429" in str(excinfo.value) or "Rate limited" in str(excinfo.value)
