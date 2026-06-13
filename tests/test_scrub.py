"""Scrubbing unit tests: planted secrets must never survive scrub()."""

from __future__ import annotations

from akamai_cloud_mcp.scrub import REDACTED, scrub, scrub_text

FAKE_KUBECONFIG = (
    "apiVersion: v1\nclusters:\n- cluster:\n    server: https://example\n"
    "kind: Config\ncurrent-context: lke\n"
)
# Fake, non-real 64-hex token shape.
FAKE_TOKEN = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
FAKE_JWT = "eyJhbGciOi.eyJzdWIiOiYWFh.c2lnbmF0dXJlX29r"
FAKE_PEM = "-----BEGIN PRIVATE KEY-----\nMIIabc\n-----END PRIVATE KEY-----"


def test_redacts_kubeconfig_key() -> None:
    out = scrub({"label": "prod", "kubeconfig": FAKE_KUBECONFIG})
    assert out["label"] == "prod"
    assert out["kubeconfig"] == REDACTED


def test_redacts_access_and_secret_keys() -> None:
    out = scrub({"access_key": "AKIA-fake", "secret_key": "shh", "id": 7})
    assert out["access_key"] == REDACTED
    assert out["secret_key"] == REDACTED
    assert out["id"] == 7


def test_redacts_kubeconfig_value_under_innocent_key() -> None:
    # Escape-hatch case: the secret arrives under an unexpected key name.
    out = scrub({"blob": FAKE_KUBECONFIG})
    assert out["blob"] == REDACTED


def test_redacts_value_shapes() -> None:
    out = scrub(
        {
            "a": FAKE_TOKEN,
            "b": FAKE_JWT,
            "c": FAKE_PEM,
            "d": "Bearer abc.def.ghi",
        }
    )
    assert out["a"] == REDACTED
    assert out["b"] == REDACTED
    assert out["c"] == REDACTED
    assert out["d"] == REDACTED


def test_keeps_normal_values() -> None:
    payload = {
        "id": 123,
        "label": "my-instance",
        "region": "us-east",
        "status": "running",
        "tags": ["prod", "web"],
        "ipv4": ["192.0.2.10"],
    }
    assert scrub(payload) == payload


def test_recurses_nested_structures() -> None:
    out = scrub({"items": [{"token": "x"}, {"name": "ok"}]})
    assert out["items"][0]["token"] == REDACTED
    assert out["items"][1]["name"] == "ok"


def test_scrub_text_redacts_token_shape() -> None:
    line = f"failed with token {FAKE_TOKEN} oops"
    assert FAKE_TOKEN not in scrub_text(line)
