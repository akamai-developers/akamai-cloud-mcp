"""Compute domain (tag: compute).

Tools: list_instances, get_instance, list_volumes.
All read-only. Built by allowlist serializers and passed through scrub(). These
tools use the account, so a token is required.
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.domains._helpers import READ_ONLY, Detail, cap, project
from akamai_cloud_mcp.errors import map_api_error
from akamai_cloud_mcp.scrub import scrub
from akamai_cloud_mcp.serialize import serialize_instance, serialize_volume


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Compute tools on the given FastMCP server."""

    @mcp.tool(
        name="linode_list_instances",
        tags={"compute"},
        annotations=READ_ONLY,
        description=(
            "List the Linode compute instances in the account, with region, type, "
            "status, IPs, image, and specs. Use to inventory what is running."
        ),
    )
    def list_instances(detail: Detail | None = None) -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/linode/instances")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "instances": [
                project(serialize_instance(r), detail or ctx.config.detail) for r in capped
            ],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} instances."
        return scrub(result)

    @mcp.tool(
        name="linode_get_instance",
        tags={"compute"},
        annotations=READ_ONLY,
        description=(
            "Get one Linode compute instance by id, with region, type, status, "
            "IPs, image, and specs."
        ),
    )
    def get_instance(instance_id: int) -> dict[str, Any]:
        try:
            resp = ctx.client.get(f"/linode/instances/{instance_id}")
        except Exception as exc:
            raise map_api_error(exc) from exc
        return scrub(serialize_instance(resp))

    @mcp.tool(
        name="linode_list_volumes",
        tags={"compute"},
        annotations=READ_ONLY,
        description=(
            "List the block storage volumes in the account, with size, region, "
            "status, and the instance each is attached to."
        ),
    )
    def list_volumes(detail: Detail | None = None) -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/volumes")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "volumes": [
                project(serialize_volume(r), detail or ctx.config.detail) for r in capped
            ],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} volumes."
        return scrub(result)
