"""LKE domain (tag: lke).

Tools: list_lke_clusters, get_lke_cluster, list_kubernetes_versions.

CRITICAL: the cluster kubeconfig is never read or returned. The allowlist
serializer does not include it, the tool never fetches
`/lke/clusters/{id}/kubeconfig`, and scrub() is the backstop if a kubeconfig-like
value ever slips into a subresource response.
"""

from __future__ import annotations

from typing import Any

from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.domains._helpers import READ_ONLY, cap, data_list
from akamai_cloud_mcp.errors import map_api_error
from akamai_cloud_mcp.scrub import scrub
from akamai_cloud_mcp.serialize import serialize_lke_cluster, serialize_lke_pool


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register LKE tools on the given FastMCP server."""

    @mcp.tool(
        name="list_lke_clusters",
        tags={"lke"},
        annotations=READ_ONLY,
        description=(
            "List the LKE (Linode Kubernetes Engine) clusters in the account, with "
            "region, Kubernetes version, tier, and control plane settings. The "
            "kubeconfig is never returned."
        ),
    )
    def list_lke_clusters() -> dict[str, Any]:
        try:
            resp = ctx.client.get("/lke/clusters")
        except Exception as exc:
            raise map_api_error(exc) from exc
        rows = data_list(resp)
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "clusters": [serialize_lke_cluster(r) for r in capped],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} clusters."
        return scrub(result)

    @mcp.tool(
        name="get_lke_cluster",
        tags={"lke"},
        annotations=READ_ONLY,
        description=(
            "Get one LKE cluster by id with its node pools, API endpoints, control "
            "plane ACL, and dashboard URL. The kubeconfig is never read or "
            "returned, even if asked."
        ),
    )
    def get_lke_cluster(cluster_id: int) -> dict[str, Any]:
        try:
            cluster = ctx.client.get(f"/lke/clusters/{cluster_id}")
        except Exception as exc:
            raise map_api_error(exc) from exc

        result: dict[str, Any] = {"cluster": serialize_lke_cluster(cluster)}
        warnings: list[str] = []

        # Subresources are best-effort; a failure on one degrades gracefully and
        # never blocks the rest. The kubeconfig endpoint is intentionally absent.
        try:
            pools = data_list(ctx.client.get(f"/lke/clusters/{cluster_id}/pools"))
            result["pools"] = [serialize_lke_pool(p) for p in pools]
        except Exception:
            warnings.append("Could not load node pools.")

        try:
            endpoints = data_list(ctx.client.get(f"/lke/clusters/{cluster_id}/api-endpoints"))
            result["api_endpoints"] = endpoints
        except Exception:
            warnings.append("Could not load API endpoints.")

        try:
            acl = ctx.client.get(f"/lke/clusters/{cluster_id}/control_plane_acl")
            result["control_plane_acl"] = acl.get("acl") if isinstance(acl, dict) else acl
        except Exception:
            warnings.append("Could not load control plane ACL.")

        try:
            dashboard = ctx.client.get(f"/lke/clusters/{cluster_id}/dashboard")
            result["dashboard_url"] = (
                dashboard.get("url") if isinstance(dashboard, dict) else None
            )
        except Exception:
            warnings.append("Could not load dashboard URL.")

        if warnings:
            result["warnings"] = warnings
        return scrub(result)

    @mcp.tool(
        name="list_kubernetes_versions",
        tags={"lke"},
        annotations=READ_ONLY,
        description=(
            "List the Kubernetes versions available for new and upgraded LKE "
            "clusters."
        ),
    )
    def list_kubernetes_versions() -> dict[str, Any]:
        try:
            resp = ctx.client.get("/lke/versions")
        except Exception as exc:
            raise map_api_error(exc) from exc
        rows = data_list(resp)
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "versions": capped,
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} versions."
        return scrub(result)
