"""Recursive response scrubbing: the backstop that runs on every tool return.

Defense in depth. Allowlist serialization (serialize.py) is the primary control:
secret-bearing fields are never copied out of the SDK object in the first place.
This module is the recursive backstop, applied to every tool return and to the
escape hatch where field names are unknown ahead of time.

Two independent redaction signals:

1. Key-name matching: a dict key that looks like it holds a secret or a
   payment/PII field gets its value replaced wholesale.
2. Value-shape heuristics: a string value that looks like a PEM block, a
   base64 kubeconfig, a JWT, a bearer token, or a high-entropy secret gets
   redacted no matter what key it sits under.
"""

from __future__ import annotations

import math
import re
from typing import Any

REDACTED = "[REDACTED]"

# Substrings (case-insensitive) that mark a dict key as secret- or PII-bearing.
# Matched as substrings so "customer_secret_key" and "x-api-token" both trip.
_SECRET_KEY_SUBSTRINGS = (
    "kubeconfig",
    "secret",
    "password",
    "passwd",
    "token",
    "credential",
    "private_key",
    "privatekey",
    "access_key",
    "accesskey",
    "secret_key",
    "secretkey",
    "api_key",
    "apikey",
    "client_secret",
    "session_key",
    "auth",
    # payment-method / PII fields
    "card_number",
    "card_type",
    "cvv",
    "cvc",
    "ccv",
    "security_code",
    "payment_method",
    "payment_methods",
    "expiry",
    "exp_month",
    "exp_year",
    "tax_id",
    "ssn",
)

# Account-holder PII fields, matched by EXACT key name (not substring) so we do
# not redact lookalikes - notably "address" (an IP address that list_ips returns)
# must survive, while "address_1"/"address_2" (street address) must not. These
# are the fields a raw /account read would otherwise hand the model through the
# escape hatch, which the allowlist serializers strip on the curated paths.
_PII_KEYS = frozenset(
    {
        "first_name",
        "last_name",
        "email",
        "phone",
        "address_1",
        "address_2",
        "city",
        "state",
        "zip",
        "credit_card",
        "last_four",
        "paypal",
    }
)

# Keys that contain a secret substring but are safe (allowlisted past the filter).
# "authorized" / "authorized_keys count" style fields are not credentials, but a
# raw authorized_keys VALUE could be, so we do NOT allowlist those here.
_KEY_ALLOWLIST = (
    "token_count",
    "authorized",  # boolean flags like "authorized: true"
)

_PEM_RE = re.compile(r"-----BEGIN [A-Z ]+-----")
_JWT_RE = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$")
_BEARER_RE = re.compile(r"^Bearer\s+\S+", re.IGNORECASE)
# kubeconfig YAML markers (raw or inside a value)
_KUBECONFIG_MARKERS = ("apiVersion: v1", "clusters:", "current-context:", "kind: Config")

# Linode personal access tokens are 64 lowercase-hex characters.
_LINODE_TOKEN_RE = re.compile(r"^[0-9a-f]{64}$")


def _key_is_secret(key: str) -> bool:
    lowered = key.lower()
    if lowered in _PII_KEYS:
        return True
    if any(allowed == lowered for allowed in _KEY_ALLOWLIST):
        return False
    return any(sub in lowered for sub in _SECRET_KEY_SUBSTRINGS)


def _shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    length = len(value)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def _looks_like_secret_value(value: str) -> bool:
    """Value-shape heuristics. Conservative to avoid redacting normal data."""
    stripped = value.strip()
    if not stripped:
        return False
    if _PEM_RE.search(stripped):
        return True
    if _BEARER_RE.match(stripped):
        return True
    if _LINODE_TOKEN_RE.match(stripped):
        return True
    if _JWT_RE.match(stripped):
        return True
    if any(marker in stripped for marker in _KUBECONFIG_MARKERS):
        return True
    # High-entropy backstop: only fire on long, unbroken, secret-shaped tokens.
    # Real labels and descriptions contain spaces and punctuation; require none.
    if len(stripped) >= 40 and " " not in stripped and "\n" not in stripped:
        # Mostly base64 / hex alphabet.
        if re.fullmatch(r"[A-Za-z0-9+/=_-]+", stripped) and _shannon_entropy(stripped) >= 4.0:
            return True
    return False


def scrub(value: Any) -> Any:
    """Return a deep-redacted copy of an arbitrary JSON-like structure.

    Never mutates the input. Dict keys flagged as secret have their value
    replaced; string values that look like secrets are replaced regardless of key.
    """
    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and _key_is_secret(k):
                result[k] = REDACTED
            else:
                result[k] = scrub(v)
        return result
    if isinstance(value, (list, tuple)):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        if _looks_like_secret_value(value):
            return REDACTED
        return value
    return value


def scrub_text(text: str) -> str:
    """Redact secret-shaped substrings from a free-text string (for log lines)."""
    if not text:
        return text
    redacted = _PEM_RE.sub(REDACTED, text)
    redacted = re.sub(r"Bearer\s+\S+", REDACTED, redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"\b[0-9a-f]{64}\b", REDACTED, redacted)
    return redacted
