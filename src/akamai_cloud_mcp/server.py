"""Server construction and CLI entry point.

`build_server` is the single construction path shared by the CLI and the tests.
It wires conditional domain registration: only selected domains register tools,
so an unselected domain registers zero tools (the version-proof anti-bloat
control). `run` parses CLI flags, resolves the transport, and enforces the
HTTP-auth default before serving.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from typing import Any

from fastmcp import FastMCP

from akamai_cloud_mcp import __version__
from akamai_cloud_mcp.client import LinodeClientWrapper
from akamai_cloud_mcp.config import Config, parse_domains
from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.domains import get_registrars

logger = logging.getLogger("akamai_cloud_mcp")

HTTP_AUTH_TOKEN_ENV = "AKAMAI_MCP_HTTP_AUTH_TOKEN"
ALLOW_INSECURE_HTTP_ENV = "AKAMAI_MCP_ALLOW_INSECURE_HTTP"

SERVER_INSTRUCTIONS = (
    "Read-only access to Akamai Cloud (Linode): inventory, pricing, and account "
    "limits. Every tool is read-only; secrets (kubeconfigs, access keys, tokens, "
    "payment and PII fields) are scrubbed from results. Use linode_api_get for "
    "any read not covered by a curated tool."
)

_UNSET = object()


def build_server(
    domains: str | Sequence[str] = "all",
    *,
    config: Config | None = None,
    token: Any = _UNSET,
    auth: Any = None,
) -> FastMCP:
    """Build and return a configured FastMCP server.

    domains: "all", a comma string, or a sequence of domain names.
    config:  an explicit Config; otherwise built from the environment.
    token:   an explicit Linode token; otherwise loaded from the environment
             (not required at construction time, only when a tool calls the API).
    auth:    an optional FastMCP auth provider (used for the HTTP transport).
    """
    if config is None:
        config = Config.from_env()

    if isinstance(domains, str):
        config.domains = parse_domains(domains)
    else:
        config.domains = parse_domains(",".join(domains))

    if token is _UNSET:
        from akamai_cloud_mcp.auth import load_token

        token = load_token(required=False)

    client = LinodeClientWrapper(config, token)
    ctx = ServerContext(config=config, client=client)

    mcp = FastMCP(
        name="akamai-cloud-mcp",
        version=__version__,
        instructions=SERVER_INSTRUCTIONS,
        auth=auth,
    )

    registrars = get_registrars()
    for name in config.domains:
        registrars[name](mcp, ctx)

    return mcp


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="akamai-cloud-mcp",
        description="Read-only MCP server for Akamai Cloud (Linode).",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "http"],
        default=None,
        help="Transport to serve (default: stdio; 'http' is an alias for streamable-http).",
    )
    parser.add_argument("--host", default=None, help="HTTP bind host (default 127.0.0.1).")
    parser.add_argument("--port", type=int, default=None, help="HTTP bind port (default 8080).")
    parser.add_argument("--path", default=None, help="HTTP path (default /mcp).")
    parser.add_argument(
        "--domains",
        default=None,
        help="Comma-separated domains to load, or 'all' (default). Choices: "
        "regions,pricing,compute,lke,object_storage,networking,account,dns,databases,escape.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="Cap rows returned by list_* tools (default 50).",
    )
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Disabled seam for future write tools. v1 ships none; this gates nothing.",
    )
    parser.add_argument("--version", action="version", version=f"akamai-cloud-mcp {__version__}")
    return parser


def _resolve_config(args: argparse.Namespace) -> Config:
    config = Config.from_env()
    if args.transport is not None:
        config.transport = "streamable-http" if args.transport == "http" else args.transport
    if args.host is not None:
        config.host = args.host
    if args.port is not None:
        config.port = args.port
    if args.path is not None:
        config.path = args.path
    if args.domains is not None:
        config.domains = parse_domains(args.domains)
    if args.max_results is not None:
        config.max_results = args.max_results
    if args.allow_write:
        # v1 ships no write tools, so this flag intentionally gates nothing.
        config.allow_write = True
        logger.warning("--allow-write set, but v1 ships no write tools. Ignoring.")
    return config


def _http_auth_or_refuse() -> Any:
    """Return an auth provider for the HTTP transport, or exit if none configured.

    A server that can return account, billing, and PII data must not start the
    HTTP transport wide open. We require a static bearer token via
    AKAMAI_MCP_HTTP_AUTH_TOKEN, or refuse to start unless the operator has
    explicitly opted into an insecure run.
    """
    token = os.environ.get(HTTP_AUTH_TOKEN_ENV)
    if token:
        from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

        return StaticTokenVerifier(tokens={token: {"client_id": "akamai-cloud-mcp"}})

    if os.environ.get(ALLOW_INSECURE_HTTP_ENV) == "1":
        sys.stderr.write(
            "\n"
            "############################################################\n"
            "# WARNING: HTTP transport starting with NO AUTHENTICATION.  #\n"
            "# Anyone who can reach this port can read account, billing, #\n"
            "# and PII data from the single shared server-side token.    #\n"
            "# Put it behind auth and TLS before exposing it.            #\n"
            "############################################################\n\n"
        )
        return None

    sys.stderr.write(
        f"Refusing to start HTTP transport without auth. Set {HTTP_AUTH_TOKEN_ENV} to a "
        "bearer token clients must present, or set "
        f"{ALLOW_INSECURE_HTTP_ENV}=1 to override (not recommended).\n"
    )
    raise SystemExit(2)


def run(argv: Sequence[str] | None = None) -> None:
    """CLI entry point: parse flags, build the server, serve on the transport."""
    logging.basicConfig(level=logging.INFO)
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    config = _resolve_config(args)

    auth = None
    if config.transport in ("streamable-http", "http"):
        auth = _http_auth_or_refuse()

    mcp = build_server(domains=config.domains, config=config, auth=auth)

    if config.transport == "stdio":
        mcp.run()
    else:
        mcp.run(
            transport="streamable-http",
            host=config.host,
            port=config.port,
            path=config.path,
            stateless_http=config.stateless_http,
        )


if __name__ == "__main__":
    run()
