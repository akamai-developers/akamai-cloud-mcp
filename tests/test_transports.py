"""Transport construction and the HTTP-auth default."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

from akamai_cloud_mcp.server import (
    ALLOW_INSECURE_HTTP_ENV,
    HTTP_AUTH_TOKEN_ENV,
    _http_auth_or_refuse,
    build_server,
)


def test_stdio_server_constructs() -> None:
    assert isinstance(build_server(domains="all"), FastMCP)


def test_http_refuses_without_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HTTP_AUTH_TOKEN_ENV, raising=False)
    monkeypatch.delenv(ALLOW_INSECURE_HTTP_ENV, raising=False)
    with pytest.raises(SystemExit) as excinfo:
        _http_auth_or_refuse()
    assert excinfo.value.code == 2


def test_http_returns_verifier_with_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(HTTP_AUTH_TOKEN_ENV, "test-bearer-token")
    monkeypatch.delenv(ALLOW_INSECURE_HTTP_ENV, raising=False)
    verifier = _http_auth_or_refuse()
    assert verifier is not None


def test_http_insecure_override_allows_no_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HTTP_AUTH_TOKEN_ENV, raising=False)
    monkeypatch.setenv(ALLOW_INSECURE_HTTP_ENV, "1")
    # Returns None (no verifier) but does not exit.
    assert _http_auth_or_refuse() is None
