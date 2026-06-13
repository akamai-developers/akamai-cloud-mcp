"""Object Storage domain (tag: object_storage).

Tools: list_object_storage_buckets, list_object_storage_endpoints,
get_object_storage_transfer, list_object_storage_quotas.

Access and secret keys are NEVER returned. There is no key-listing tool. The
deprecated clusters endpoint is not used; endpoints() is used instead.
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.domains._helpers import READ_ONLY, cap
from akamai_cloud_mcp.errors import map_api_error
from akamai_cloud_mcp.scrub import scrub
from akamai_cloud_mcp.serialize import serialize_bucket


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Object Storage tools on the given FastMCP server."""

    @mcp.tool(
        name="list_object_storage_buckets",
        tags={"object_storage"},
        annotations=READ_ONLY,
        description=(
            "List Object Storage buckets, optionally scoped to one region, with "
            "hostname, endpoint type, size, and object count. Access keys are never "
            "returned."
        ),
    )
    def list_object_storage_buckets(region: str | None = None) -> dict[str, Any]:
        path = f"/object-storage/buckets/{region}" if region else "/object-storage/buckets"
        try:
            rows = ctx.client.get_all(path)
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "region": region,
            "count": len(capped),
            "capped": was_capped,
            "buckets": [serialize_bucket(r) for r in capped],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} buckets."
        return scrub(result)

    @mcp.tool(
        name="get_object_storage_bucket",
        tags={"object_storage"},
        annotations=READ_ONLY,
        description=(
            "Get details for a single Object Storage bucket by region and name "
            "(hostname, S3 endpoint, endpoint type, size, and object count). Access "
            "keys are never returned."
        ),
    )
    def get_object_storage_bucket(region: str, bucket: str) -> dict[str, Any]:
        try:
            resp = ctx.client.get(f"/object-storage/buckets/{region}/{bucket}")
        except Exception as exc:
            raise map_api_error(exc) from exc
        return scrub(serialize_bucket(resp))

    @mcp.tool(
        name="list_object_storage_endpoints",
        tags={"object_storage"},
        annotations=READ_ONLY,
        description=(
            "List Object Storage endpoints (region, endpoint type, and S3 "
            "hostname) available to the account."
        ),
    )
    def list_object_storage_endpoints() -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/object-storage/endpoints")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "endpoints": capped,
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} endpoints."
        return scrub(result)

    @mcp.tool(
        name="get_object_storage_transfer",
        tags={"object_storage"},
        annotations=READ_ONLY,
        description=(
            "Get the account's Object Storage network transfer for the current "
            "billing period (used, quota, and billable)."
        ),
    )
    def get_object_storage_transfer() -> dict[str, Any]:
        try:
            resp = ctx.client.get("/object-storage/transfer")
        except Exception as exc:
            raise map_api_error(exc) from exc
        return scrub(resp)

    @mcp.tool(
        name="list_object_storage_quotas",
        tags={"object_storage"},
        annotations=READ_ONLY,
        description=(
            "List Object Storage quotas for the account. This is the only quota API "
            "Linode exposes; it is scoped to Object Storage, not the whole account."
        ),
    )
    def list_object_storage_quotas() -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/object-storage/quotas")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "quotas": capped,
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} quotas."
        return scrub(result)
