"""Managed Databases domain (tag: databases).

Tools: list_databases, get_database, list_database_engines, list_database_types.
All read-only, allowlist-serialized, and scrubbed.

CRITICAL: connection credentials (root_username/root_password) live on
`/databases/{engine}/instances/{id}/credentials` and the CA cert on `.../ssl`.
Those subendpoints have no tool and are denylisted in the escape hatch. The
allowlist serializer never names a credential field, and the tools never read the
SDK `.credentials`/`.ssl` lazy properties (which would trigger a fetch).
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.domains._helpers import READ_ONLY, cap
from akamai_cloud_mcp.errors import ToolError, map_api_error
from akamai_cloud_mcp.scrub import scrub
from akamai_cloud_mcp.serialize import (
    serialize_database,
    serialize_database_engine,
    serialize_database_type,
)

# Engines with a per-instance GET path. get_database routes by engine; validating
# the argument here also blocks path injection into /databases/{engine}/...
DATABASE_ENGINES = ("mysql", "postgresql")


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Managed Databases tools on the given FastMCP server."""

    @mcp.tool(
        name="linode_list_databases",
        tags={"databases"},
        annotations=READ_ONLY,
        description=(
            "List the Managed Database clusters in the account (all engines), with "
            "engine, version, region, status, plan, cluster size, and host. The "
            "root password is never returned."
        ),
    )
    def list_databases() -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/databases/instances")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "databases": [serialize_database(r) for r in capped],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} databases."
        return scrub(result)

    @mcp.tool(
        name="linode_get_database",
        tags={"databases"},
        annotations=READ_ONLY,
        description=(
            "Get one Managed Database by engine and id, with version, region, "
            "status, host, port, and maintenance window. engine must be 'mysql' or "
            "'postgresql' (take it from linode_list_databases). The root password is never "
            "returned."
        ),
    )
    def get_database(engine: str, database_id: int) -> dict[str, Any]:
        eng = engine.strip().lower()
        if eng not in DATABASE_ENGINES:
            raise ToolError(
                f"Unknown database engine '{engine}'. Valid engines: "
                f"{', '.join(DATABASE_ENGINES)}."
            )
        try:
            resp = ctx.client.get(f"/databases/{eng}/instances/{database_id}")
        except Exception as exc:
            raise map_api_error(exc) from exc
        return scrub({"database": serialize_database(resp)})

    @mcp.tool(
        name="linode_list_database_engines",
        tags={"databases"},
        annotations=READ_ONLY,
        description=(
            "List the database engines and versions available for new Managed "
            "Database clusters."
        ),
    )
    def list_database_engines() -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/databases/engines")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "engines": [serialize_database_engine(r) for r in capped],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} engines."
        return scrub(result)

    @mcp.tool(
        name="linode_list_database_types",
        tags={"databases"},
        annotations=READ_ONLY,
        description=(
            "List the Managed Database plan types with vcpus, memory, disk, "
            "supported engines, and price."
        ),
    )
    def list_database_types() -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/databases/types")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "types": [serialize_database_type(r) for r in capped],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} types."
        return scrub(result)
