"""Regions & Catalog domain (tag: regions).

Tools: list_regions, get_region_availability, list_instance_types.
All read-only. Built by allowlist serializers and passed through scrub().
These endpoints are public, so they work even without a token configured.
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.errors import map_api_error
from akamai_cloud_mcp.scrub import scrub
from akamai_cloud_mcp.serialize import serialize_region, serialize_type

READ_ONLY = {"readOnlyHint": True}


def _data_list(resp: Any) -> list[Any]:
    """Extract the row list from a paged response, a bare list, or a single dict."""
    if isinstance(resp, dict) and "data" in resp:
        data = resp["data"]
        return data if isinstance(data, list) else [data]
    if isinstance(resp, list):
        return resp
    return [resp]


def _cap(rows: list[Any], max_results: int) -> tuple[list[Any], bool]:
    if len(rows) > max_results:
        return rows[:max_results], True
    return rows, False


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Regions & Catalog tools on the given FastMCP server."""

    @mcp.tool(
        name="linode_list_regions",
        tags={"regions"},
        annotations=READ_ONLY,
        description=(
            "List Akamai Cloud (Linode) regions with their capabilities, country, "
            "site type, and status. Use to see where you can deploy."
        ),
    )
    def list_regions() -> dict[str, Any]:
        try:
            resp = ctx.client.cached_get("/regions")
        except Exception as exc:
            raise map_api_error(exc) from exc
        rows = _data_list(resp)
        capped, was_capped = _cap(rows, ctx.config.max_results)
        result = {
            "count": len(capped),
            "capped": was_capped,
            "regions": [serialize_region(r) for r in capped],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} regions."
        return scrub(result)

    @mcp.tool(
        name="linode_get_region_availability",
        tags={"regions"},
        annotations=READ_ONLY,
        description=(
            "Show which plans are in stock. With no argument, returns account-wide "
            "regional availability. Pass a region id (for example 'us-east') to "
            "scope it to one region. Use this to find where a plan is available."
        ),
    )
    def get_region_availability(region: str | None = None) -> dict[str, Any]:
        try:
            if region:
                resp = ctx.client.public_get_all(f"/regions/{region}/availability")
            else:
                resp = ctx.client.public_get_all("/regions/availability")
        except Exception as exc:
            raise map_api_error(exc) from exc
        rows = _data_list(resp)
        capped, was_capped = _cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "region": region,
            "count": len(capped),
            "capped": was_capped,
            "availability": capped,
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} rows."
        return scrub(result)

    @mcp.tool(
        name="linode_list_instance_types",
        tags={"regions"},
        annotations=READ_ONLY,
        description=(
            "List Linode instance plan types with vcpus, memory, disk, transfer, "
            "gpus, accelerated_devices, class, default price, and region price "
            "overrides. Use to compare plans or find a type id for cost estimates."
        ),
    )
    def list_instance_types() -> dict[str, Any]:
        try:
            resp = ctx.client.cached_get("/linode/types")
        except Exception as exc:
            raise map_api_error(exc) from exc
        rows = _data_list(resp)
        capped, was_capped = _cap(rows, ctx.config.max_results)
        result = {
            "count": len(capped),
            "capped": was_capped,
            "types": [serialize_type(t) for t in capped],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} types."
        return scrub(result)
