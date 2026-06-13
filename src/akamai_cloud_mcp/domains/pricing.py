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

from typing import Any

from akamai_cloud_mcp.context import ServerContext
from akamai_cloud_mcp.errors import ToolError, map_api_error
from akamai_cloud_mcp.pricing_supplement import object_storage_request_pricing
from akamai_cloud_mcp.scrub import scrub

READ_ONLY = {"readOnlyHint": True}

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
