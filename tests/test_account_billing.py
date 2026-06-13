"""Phase 7: Account & Billing tools. PII and payment fields must be redacted."""

from __future__ import annotations

import json
from typing import Any

from fastmcp.client import Client

from akamai_cloud_mcp.server import build_server
from tests.conftest import _FAKE_CARD, _FAKE_EMAIL, _FAKE_PHONE


async def _call(mcp: Any, name: str, args: dict[str, Any] | None = None) -> Any:
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
        return result.data


async def _tool_names(mcp: Any) -> set[str]:
    async with Client(mcp) as client:
        return {t.name for t in await client.list_tools()}


async def test_account_tools_register() -> None:
    names = await _tool_names(build_server(domains="account"))
    assert {
        "linode_get_account",
        "linode_get_account_transfer",
        "linode_list_invoices",
        "linode_list_events",
        "linode_get_account_limits",
    } <= names


async def test_account_domain_toggle_off() -> None:
    # CRITICAL: dropping the account domain removes exactly its tools.
    names = await _tool_names(build_server(domains="compute,pricing"))
    for tool in (
        "linode_get_account",
        "linode_get_account_transfer",
        "linode_list_invoices",
        "linode_list_events",
        "linode_get_account_limits",
    ):
        assert tool not in names


async def test_get_account_redacts_pii_and_payment(mock_get: None) -> None:
    data = await _call(build_server(domains="account"), "linode_get_account")
    assert data["company"] == "Example Co"
    assert data["country"] == "US"
    # PII / payment must be absent.
    pii_fields = ("first_name", "last_name", "email", "phone", "address_1", "credit_card", "tax_id")
    for field in pii_fields:
        assert field not in data
    blob = json.dumps(data)
    assert _FAKE_EMAIL not in blob
    assert _FAKE_PHONE not in blob
    assert _FAKE_CARD not in blob


async def test_get_account_transfer(mock_get: None) -> None:
    data = await _call(build_server(domains="account"), "linode_get_account_transfer")
    assert data["quota"] == 1024
    assert data["region_transfers"][0]["id"] == "us-east"


async def test_list_invoices_no_payment_detail(mock_get: None) -> None:
    data = await _call(build_server(domains="account"), "linode_list_invoices")
    inv = data["invoices"][0]
    assert inv["total"] == 106.0
    assert "payment_method" not in inv
    assert _FAKE_CARD not in json.dumps(data)


async def test_list_events(mock_get: None) -> None:
    data = await _call(build_server(domains="account"), "linode_list_events")
    assert data["events"][0]["action"] == "linode_boot"


async def test_get_account_limits_composed(mock_get: None) -> None:
    data = await _call(build_server(domains="account"), "linode_get_account_limits")
    assert "does not expose a single" in data["summary"]
    assert len(data["rate_limits"]["limits"]) >= 1
    # Object Storage quotas come from the only quota API Linode exposes.
    assert data["object_storage_quotas"][0]["resource_metric"] == "bucket"
    assert data["transfer_pool"]["quota"] == 1024
