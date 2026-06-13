"""Pricing & cost domain (tag: pricing).

Tools: get_pricing (this phase); find_gpu_availability and estimate_cost land in
Phase 2b. Pricing uses public type/price endpoints and works without a token.

Two pricing facts this module enforces, both easy to get wrong:

- region price fallback: top-level `price` is the default-region price;
  `region_prices[]` lists overrides for higher-cost regions only. To price a
  region, match its id in `region_prices[]`, else fall back to top-level `price`.
- null monthly: metered SKUs report `price.monthly == null` (not 0). Null means
  "priced per unit, no monthly cap." Never coerce null to 0.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.errors import ToolError, map_api_error
from akamai_cloud_mcp.pricing_supplement import (
    object_storage_allotments,
    object_storage_request_pricing,
    transfer_pool,
)
from akamai_cloud_mcp.scrub import scrub

READ_ONLY = {"readOnlyHint": True}

# Hours per month used to derive an hourly figure for monthly-priced supplement
# items. Live API items use their own hourly price directly.
HOURS_PER_MONTH = 730

# GPU SKUs that are marketing-listed but absent from /linode/types (not
# self-serve priced). Surfaced by find_gpu_availability so the model does not
# report them as missing.
MARKETING_ONLY_GPUS = [
    {
        "id": "rtx-pro-6000-blackwell",
        "label": "RTX PRO 6000 Blackwell",
        "status": "by request",
        "note": "Contact sales; not self-serve priced and absent from /linode/types.",
    }
]


# -- estimate_cost pinned input model (do not change shape across sessions) ----


class InstanceSpec(BaseModel):
    type: str
    count: int = 1
    backups: bool = False


class VolumeSpec(BaseModel):
    size_gb: int
    count: int = 1


class ObjectStorageSpec(BaseModel):
    storage_gb: float = 0
    class_a_requests: int = 0
    class_b_requests: int = 0
    egress_gb: float = 0


class EstimateRequest(BaseModel):
    region: str | None = None
    instances: list[InstanceSpec] = Field(default_factory=list)
    volumes: list[VolumeSpec] = Field(default_factory=list)
    nodebalancers: int = 0
    lke_tier: Literal["none", "standard", "ha", "enterprise"] = "none"
    object_storage: ObjectStorageSpec | None = None
    extra_egress_gb: float = 0

# Product family -> public price/type endpoint.
FAMILY_ENDPOINTS = {
    "compute": "/linode/types",
    "block_storage": "/volumes/types",
    "nodebalancers": "/nodebalancers/types",
    "network_transfer": "/network-transfer/prices",
    "lke": "/lke/types",
    "object_storage": "/object-storage/types",
}


def resolve_region_price(entry: dict[str, Any], region: str | None) -> dict[str, Any]:
    """Return {hourly, monthly} for a region, with the documented fallback.

    Monthly stays None when the API reports null (metered SKU); never coerced.
    """
    base = entry.get("price") or {}
    if region:
        for override in entry.get("region_prices") or []:
            if isinstance(override, dict) and override.get("id") == region:
                return {"hourly": override.get("hourly"), "monthly": override.get("monthly")}
    return {"hourly": base.get("hourly"), "monthly": base.get("monthly")}


def _data_list(resp: Any) -> list[Any]:
    if isinstance(resp, dict) and "data" in resp:
        data = resp["data"]
        return data if isinstance(data, list) else [data]
    if isinstance(resp, list):
        return resp
    return [resp]


def _index_by_id(rows: list[Any]) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in rows if isinstance(r, dict) and "id" in r}


def _resolve_addon_price(addon: dict[str, Any], region: str | None) -> dict[str, Any]:
    """Resolve an addon's price (for example backups) with region fallback."""
    base = addon.get("price") or {}
    if region:
        for override in addon.get("region_prices") or []:
            if isinstance(override, dict) and override.get("id") == region:
                return {"hourly": override.get("hourly"), "monthly": override.get("monthly")}
    return {"hourly": base.get("hourly"), "monthly": base.get("monthly")}


def _line(
    category: str, detail: str, source: str, hourly: float, monthly: float
) -> dict[str, Any]:
    return {
        "category": category,
        "detail": detail,
        "source": source,
        "hourly": round(hourly, 6),
        "monthly": round(monthly, 4),
    }


# LKE tier -> control-plane type id.
LKE_TIER_TYPES = {"standard": "lke-sa", "ha": "lke-ha", "enterprise": "lke-e"}


def register(mcp: Any, ctx: ServerContext) -> None:
    """Register Pricing & cost tools on the given FastMCP server."""

    @mcp.tool(
        name="get_pricing",
        tags={"pricing"},
        annotations=READ_ONLY,
        description=(
            "Get per-type pricing for a product family, optionally for a specific "
            "region. Families: compute, block_storage, nodebalancers, "
            "network_transfer, lke, object_storage. Returns hourly and monthly "
            "prices with the correct region override applied (falling back to the "
            "default price when a region has no override). Monthly is null for "
            "metered SKUs, which means priced per unit with no monthly cap."
        ),
    )
    def get_pricing(family: str, region: str | None = None) -> dict[str, Any]:
        fam = family.strip().lower()
        if fam not in FAMILY_ENDPOINTS:
            raise ToolError(
                f"Unknown pricing family '{family}'. Valid families: "
                f"{', '.join(sorted(FAMILY_ENDPOINTS))}."
            )
        try:
            resp = ctx.client.cached_get(FAMILY_ENDPOINTS[fam])
        except Exception as exc:
            raise map_api_error(exc) from exc

        rows = _data_list(resp)
        items: list[dict[str, Any]] = []
        for entry in rows[: ctx.config.max_results]:
            if not isinstance(entry, dict):
                continue
            priced = resolve_region_price(entry, region)
            items.append(
                {
                    "id": entry.get("id"),
                    "label": entry.get("label"),
                    "hourly": priced["hourly"],
                    "monthly": priced["monthly"],
                    "default_price": entry.get("price"),
                    "region_prices": entry.get("region_prices"),
                    "source": "live API",
                }
            )

        result: dict[str, Any] = {
            "family": fam,
            "region": region,
            "count": len(items),
            "capped": len(rows) > ctx.config.max_results,
            "items": items,
        }
        if fam == "object_storage":
            # The API does not express request pricing; surface the supplement.
            result["request_pricing_supplement"] = object_storage_request_pricing()
            result["note"] = (
                "Object Storage request pricing (Class A/B) is not in the API and "
                "comes from the in-repo curated supplement."
            )
        return scrub(result)

    @mcp.tool(
        name="find_gpu_availability",
        tags={"pricing"},
        annotations=READ_ONLY,
        description=(
            "Find GPU and accelerated compute plans plus where they are in stock. "
            "Returns both the gpu class (NVIDIA RTX plans) and the accelerated "
            "class (for example NETINT VPU plans), each with price and the regions "
            "where the plan is currently available. Optionally scope to one region. "
            "Marketing-only SKUs that are not self-serve priced are listed "
            "separately."
        ),
    )
    def find_gpu_availability(region: str | None = None) -> dict[str, Any]:
        try:
            types = _data_list(ctx.client.cached_get("/linode/types"))
            if region:
                avail_rows = _data_list(ctx.client.public_get(f"/regions/{region}/availability"))
            else:
                avail_rows = _data_list(ctx.client.public_get("/regions/availability"))
        except Exception as exc:
            raise map_api_error(exc) from exc

        # plan id -> sorted list of regions where it is available.
        avail_map: dict[str, list[str]] = {}
        for row in avail_rows:
            if not isinstance(row, dict) or not row.get("available"):
                continue
            plan = row.get("plan")
            reg = row.get("region")
            if plan is None or reg is None:
                continue
            avail_map.setdefault(plan, [])
            if reg not in avail_map[plan]:
                avail_map[plan].append(reg)

        def _plan_entry(entry: dict[str, Any]) -> dict[str, Any]:
            priced = resolve_region_price(entry, region)
            plan_id = entry.get("id")
            available = avail_map.get(plan_id, []) if isinstance(plan_id, str) else []
            return {
                "id": plan_id,
                "label": entry.get("label"),
                "class": entry.get("class"),
                "vcpus": entry.get("vcpus"),
                "memory": entry.get("memory"),
                "gpus": entry.get("gpus"),
                "accelerated_devices": entry.get("accelerated_devices"),
                "hourly": priced["hourly"],
                "monthly": priced["monthly"],
                "available_regions": sorted(available),
            }

        gpu_plans = [
            _plan_entry(t) for t in types if isinstance(t, dict) and t.get("class") == "gpu"
        ]
        accelerated_plans = [
            _plan_entry(t)
            for t in types
            if isinstance(t, dict) and t.get("class") == "accelerated"
        ]

        result = {
            "region": region,
            "gpu_plans": gpu_plans,
            "accelerated_plans": accelerated_plans,
            "marketing_only": MARKETING_ONLY_GPUS,
            "note": (
                "gpu class uses NVIDIA GPUs (gpus > 0); accelerated class uses "
                "dedicated accelerators such as NETINT VPUs (accelerated_devices > "
                "0, gpus == 0). Marketing-only SKUs are not self-serve priced."
            ),
        }
        return scrub(result)

    @mcp.tool(
        name="estimate_cost",
        tags={"pricing"},
        annotations=READ_ONLY,
        description=(
            "Estimate the hourly and monthly cost of a described stack: instances "
            "(with optional backups), block storage volumes, NodeBalancers, an LKE "
            "control-plane tier, and Object Storage usage. Returns itemized lines "
            "labeled by source (live API or curated supplement), the assumptions "
            "applied, and hourly and monthly totals. Free allotments are applied "
            "before overage. LKE worker nodes are priced as their underlying "
            "instance types, so add them under instances."
        ),
    )
    def estimate_cost(request: EstimateRequest) -> dict[str, Any]:
        region = request.region
        lines: list[dict[str, Any]] = []
        assumptions: list[str] = [
            f"Monthly-priced supplement items use {HOURS_PER_MONTH} hours per month "
            "to derive an hourly figure.",
        ]

        try:
            # Instances + backups.
            if request.instances:
                types = _index_by_id(_data_list(ctx.client.cached_get("/linode/types")))
                for spec in request.instances:
                    entry = types.get(spec.type)
                    if entry is None:
                        assumptions.append(f"Unknown instance type '{spec.type}'; skipped.")
                        continue
                    priced = resolve_region_price(entry, region)
                    lines.append(
                        _line(
                            "instance",
                            f"{spec.count}x {spec.type}",
                            "live API",
                            (priced["hourly"] or 0) * spec.count,
                            (priced["monthly"] or 0) * spec.count,
                        )
                    )
                    if spec.backups:
                        backups = (entry.get("addons") or {}).get("backups") or {}
                        bprice = _resolve_addon_price(backups, region)
                        lines.append(
                            _line(
                                "backups",
                                f"backups for {spec.count}x {spec.type}",
                                "live API",
                                (bprice["hourly"] or 0) * spec.count,
                                (bprice["monthly"] or 0) * spec.count,
                            )
                        )

            # Block storage volumes.
            if request.volumes:
                vtypes = _data_list(ctx.client.cached_get("/volumes/types"))
                ventry = vtypes[0] if vtypes else None
                vprice = (
                    resolve_region_price(ventry, region)
                    if isinstance(ventry, dict)
                    else {"hourly": None, "monthly": None}
                )
                for vol in request.volumes:
                    units = vol.size_gb * vol.count
                    lines.append(
                        _line(
                            "volume",
                            f"{vol.count}x {vol.size_gb}GB block storage",
                            "live API",
                            (vprice["hourly"] or 0) * units,
                            (vprice["monthly"] or 0) * units,
                        )
                    )

            # NodeBalancers.
            if request.nodebalancers:
                nbtypes = _data_list(ctx.client.cached_get("/nodebalancers/types"))
                nbentry = nbtypes[0] if nbtypes else None
                nbprice = (
                    resolve_region_price(nbentry, region)
                    if isinstance(nbentry, dict)
                    else {"hourly": None, "monthly": None}
                )
                lines.append(
                    _line(
                        "nodebalancer",
                        f"{request.nodebalancers}x NodeBalancer",
                        "live API",
                        (nbprice["hourly"] or 0) * request.nodebalancers,
                        (nbprice["monthly"] or 0) * request.nodebalancers,
                    )
                )

            # LKE control plane (workers are priced as instances).
            if request.lke_tier != "none":
                lke_id = LKE_TIER_TYPES[request.lke_tier]
                lke_types = _index_by_id(_data_list(ctx.client.cached_get("/lke/types")))
                lentry = lke_types.get(lke_id)
                if lentry is not None:
                    lprice = resolve_region_price(lentry, region)
                    lines.append(
                        _line(
                            "lke_control_plane",
                            f"LKE {request.lke_tier} control plane ({lke_id})",
                            "live API",
                            lprice["hourly"] or 0,
                            lprice["monthly"] or 0,
                        )
                    )
                assumptions.append(
                    "LKE worker nodes are priced as their underlying instance types; "
                    "include them under instances."
                )
        except Exception as exc:
            raise map_api_error(exc) from exc

        # Object Storage usage (curated supplement + allotments).
        os_spec = request.object_storage
        if os_spec is not None:
            allot = object_storage_allotments()
            req_pricing = object_storage_request_pricing()

            incl_storage = allot["included_storage_gb"]
            storage_rate = allot["storage_overage_per_gb_month"]
            storage_overage = max(0.0, os_spec.storage_gb - incl_storage)
            s_month = storage_overage * storage_rate
            lines.append(
                _line(
                    "object_storage_storage",
                    f"{os_spec.storage_gb}GB stored ({incl_storage}GB included, "
                    f"{storage_overage}GB billable)",
                    "curated supplement",
                    s_month / HOURS_PER_MONTH,
                    s_month,
                )
            )

            for klass, count in (
                ("class_a", os_spec.class_a_requests),
                ("class_b", os_spec.class_b_requests),
            ):
                info = req_pricing[klass]
                free = info["free_quota_per_month"]
                rate = info["price_per_1000"]
                overage = max(0, count - free)
                month = (overage / 1000.0) * rate
                lines.append(
                    _line(
                        f"object_storage_{klass}",
                        f"{count} {klass} requests ({free} free, {overage} billable)",
                        "curated supplement",
                        month / HOURS_PER_MONTH,
                        month,
                    )
                )

        # Network egress (Object Storage egress + extra egress) against the pool.
        total_egress = (os_spec.egress_gb if os_spec else 0) + request.extra_egress_gb
        if total_egress > 0:
            pool = transfer_pool()
            incl_transfer = pool["included_transfer_gb"]
            egress_rate = pool["overage_per_gb"]
            egress_overage = max(0.0, total_egress - incl_transfer)
            e_month = egress_overage * egress_rate
            lines.append(
                _line(
                    "network_egress",
                    f"{total_egress}GB egress ({incl_transfer}GB pool, "
                    f"{egress_overage}GB billable)",
                    "curated supplement",
                    e_month / HOURS_PER_MONTH,
                    e_month,
                )
            )
            assumptions.append(
                "Egress is estimated against the base transfer pool only; "
                "per-instance transfer allotments are not added to the pool."
            )

        total_hourly = round(sum(line["hourly"] for line in lines), 6)
        total_monthly = round(sum(line["monthly"] for line in lines), 4)

        result = {
            "region": region,
            "currency": "USD",
            "lines": lines,
            "assumptions": assumptions,
            "total_hourly": total_hourly,
            "total_monthly": total_monthly,
        }
        return scrub(result)
