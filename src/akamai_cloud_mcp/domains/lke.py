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
from akamai_cloud_mcp.domains._helpers import READ_ONLY, Detail, cap, data_list, project
from akamai_cloud_mcp.errors import map_api_error
from akamai_cloud_mcp.scrub import scrub
from akamai_cloud_mcp.serialize import serialize_lke_cluster, serialize_lke_pool


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register LKE tools on the given FastMCP server."""

    @mcp.tool(
        name="linode_list_lke_clusters",
        tags={"lke"},
        annotations=READ_ONLY,
        description=(
            "List the LKE (Linode Kubernetes Engine) clusters in the account, with "
            "region, Kubernetes version, tier, and control plane settings. The "
            "kubeconfig is never returned."
        ),
    )
    def list_lke_clusters(detail: Detail | None = None) -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/lke/clusters")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "clusters": [
                project(serialize_lke_cluster(r), detail or ctx.config.detail) for r in capped
            ],
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} clusters."
        return scrub(result)

    @mcp.tool(
        name="linode_get_lke_cluster",
        tags={"lke"},
        annotations=READ_ONLY,
        description=(
            "Get one LKE cluster by id with its node pools, API endpoints, and "
            "control plane ACL. The kubeconfig is never read or returned, even if "
            "asked."
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
            pools = ctx.client.get_all(f"/lke/clusters/{cluster_id}/pools")
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

        if warnings:
            result["warnings"] = warnings
        return scrub(result)

    @mcp.tool(
        name="linode_list_kubernetes_versions",
        tags={"lke"},
        annotations=READ_ONLY,
        description=(
            "List the Kubernetes versions available for new and upgraded LKE "
            "clusters."
        ),
    )
    def list_kubernetes_versions() -> dict[str, Any]:
        try:
            rows = ctx.client.get_all("/lke/versions")
        except Exception as exc:
            raise map_api_error(exc) from exc
        capped, was_capped = cap(rows, ctx.config.max_results)
        result: dict[str, Any] = {
            "count": len(capped),
            "capped": was_capped,
            "versions": capped,
        }
        if was_capped:
            result["note"] = f"Results capped at {ctx.config.max_results} versions."
        return scrub(result)
