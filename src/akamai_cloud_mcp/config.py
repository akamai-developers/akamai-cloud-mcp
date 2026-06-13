"""Runtime configuration: transport, network binding, domain selection, result caps.

Values come from CLI flags (parsed in `server.run`) and environment variables.
The dataclass is the single shared shape passed into `build_server`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Canonical default port for the streamable-HTTP transport.
DEFAULT_HTTP_PORT = 8080
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PATH = "/mcp"

# Cap list_* results so a tool never dumps thousands of rows into model context.
DEFAULT_MAX_RESULTS = 200

# Page size used when paginating the Linode API.
DEFAULT_PAGE_SIZE = 100

# Every domain group shipped in v1. "all" expands to this set.
ALL_DOMAINS = (
    "regions",
    "pricing",
    "compute",
    "lke",
    "object_storage",
    "networking",
    "account",
    "escape",
)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def parse_domains(spec: str | None) -> tuple[str, ...]:
    """Turn a domain spec ("all", "compute,pricing") into a validated tuple.

    Unknown domain names raise ValueError so a typo fails loudly instead of
    silently loading nothing.
    """
    if spec is None or spec.strip() == "" or spec.strip().lower() == "all":
        return ALL_DOMAINS
    requested = [part.strip().lower() for part in spec.split(",") if part.strip()]
    unknown = [d for d in requested if d not in ALL_DOMAINS]
    if unknown:
        raise ValueError(
            f"Unknown domain(s): {', '.join(unknown)}. "
            f"Valid domains: {', '.join(ALL_DOMAINS)}."
        )
    # Preserve declared order, drop duplicates.
    seen: list[str] = []
    for d in requested:
        if d not in seen:
            seen.append(d)
    return tuple(seen)


@dataclass
class Config:
    """Resolved server configuration."""

    transport: str = "stdio"
    host: str = DEFAULT_HTTP_HOST
    port: int = DEFAULT_HTTP_PORT
    path: str = DEFAULT_HTTP_PATH
    domains: tuple[str, ...] = field(default_factory=lambda: ALL_DOMAINS)
    max_results: int = DEFAULT_MAX_RESULTS
    page_size: int = DEFAULT_PAGE_SIZE
    stateless_http: bool = True
    # v1 ships no write tools. This seam stays disabled and gates nothing.
    allow_write: bool = False

    @classmethod
    def from_env(cls) -> Config:
        """Build a Config from environment variables only (CLI flags override later)."""
        transport = (_env("AKAMAI_MCP_TRANSPORT", "stdio") or "stdio").lower()
        return cls(
            transport=transport,
            host=_env("AKAMAI_MCP_HOST", DEFAULT_HTTP_HOST) or DEFAULT_HTTP_HOST,
            port=int(_env("AKAMAI_MCP_PORT", str(DEFAULT_HTTP_PORT)) or DEFAULT_HTTP_PORT),
            path=_env("AKAMAI_MCP_PATH", DEFAULT_HTTP_PATH) or DEFAULT_HTTP_PATH,
            domains=parse_domains(_env("AKAMAI_MCP_DOMAINS")),
            max_results=int(
                _env("AKAMAI_MCP_MAX_RESULTS", str(DEFAULT_MAX_RESULTS)) or DEFAULT_MAX_RESULTS
            ),
            page_size=int(
                _env("AKAMAI_MCP_PAGE_SIZE", str(DEFAULT_PAGE_SIZE)) or DEFAULT_PAGE_SIZE
            ),
        )
