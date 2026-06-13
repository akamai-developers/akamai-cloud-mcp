"""Token loading and the warn-only scope sanity check.

The Linode SDK does not read the environment itself. We read `LINODE_TOKEN`
(canonical) or `LINODE_API_TOKEN` (documented alias) and hand it to the client.
The token is never logged, echoed, or returned in any response or error.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("akamai_cloud_mcp")

TOKEN_ENV = "LINODE_TOKEN"
TOKEN_ENV_ALIAS = "LINODE_API_TOKEN"

# Read-only scopes recommended in the docs.
RECOMMENDED_SCOPES = (
    "linodes:read_only",
    "lke:read_only",
    "object_storage:read_only",
    "nodebalancers:read_only",
    "firewall:read_only",
    "vpc:read_only",
    "ips:read_only",
    "account:read_only",
    "events:read_only",
)


class MissingTokenError(RuntimeError):
    """Raised when no Linode token is present in the environment."""


def load_token(required: bool = True) -> str | None:
    """Return the Linode token from the environment, or None if absent.

    Looks at LINODE_TOKEN first, then LINODE_API_TOKEN. Raises MissingTokenError
    when `required` and neither is set. The token value is never logged.
    """
    token = os.environ.get(TOKEN_ENV) or os.environ.get(TOKEN_ENV_ALIAS)
    if token:
        token = token.strip()
    if not token:
        if required:
            raise MissingTokenError(
                f"No Linode token found. Set {TOKEN_ENV} (or {TOKEN_ENV_ALIAS}) to a "
                "read-only-scoped personal access token."
            )
        return None
    return token


def check_token_scopes(client: object) -> None:
    """Warn-only scope sanity check. Never raises, never echoes the token.

    Reads GET /profile/tokens through the client. The response carries PII and
    must be scrubbed before anything is logged. This check CANNOT detect an
    over-broad token when the token lacks profile read scope: in that case the
    call fails and we silently no-op. We never claim "scopes look fine".
    """
    from akamai_cloud_mcp.scrub import scrub

    getter = getattr(client, "get", None)
    if not callable(getter):
        return
    try:
        raw = getter("/profile/tokens")
    except Exception:
        # Token likely lacks profile read scope. We cannot inspect scopes here.
        logger.debug("Scope check skipped: profile/tokens not readable with this token.")
        return

    safe = scrub(raw)
    data = safe.get("data") if isinstance(safe, dict) else None
    if not isinstance(data, list):
        return
    for entry in data:
        if not isinstance(entry, dict):
            continue
        scopes = entry.get("scopes")
        if isinstance(scopes, str) and ("*" in scopes or "read_write" in scopes):
            logger.warning(
                "A personal access token with broad or read-write scopes was "
                "detected. This server is read-only; a read-only-scoped token is "
                "strongly recommended."
            )
            return
