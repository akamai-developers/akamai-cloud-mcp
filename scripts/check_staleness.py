"""Live pricing staleness check (scheduled CI only).

Fetches the public /linode/types endpoint (unauthenticated, verified public) and
compares the default prices of a few stable plans against
scripts/pricing_baseline.json. Exits non-zero if anything drifted, so the
scheduled job surfaces the change for a human to review and update the baseline
and the curated supplement.

This is the ONLY check that catches real catalog drift. The unit-test staleness
check runs against mocks and only exercises the diff code path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

from akamai_cloud_mcp.staleness import diff_prices

LINODE_TYPES_URL = "https://api.linode.com/v4/linode/types"
BASELINE = Path(__file__).parent / "pricing_baseline.json"


def main() -> int:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["types"]
    resp = httpx.get(LINODE_TYPES_URL, timeout=30)
    resp.raise_for_status()
    current = resp.json()["data"]

    changes = diff_prices(current, baseline)
    # diff_prices reports "added" for every live type not in the small baseline;
    # those are expected here, so only treat removed/changed as drift.
    drift = [c for c in changes if c["change"] in ("removed", "price_changed")]

    if drift:
        print("Pricing drift detected against the baseline:")
        for change in drift:
            print(json.dumps(change))
        print("\nUpdate scripts/pricing_baseline.json and the curated supplement.")
        return 1

    print("No pricing drift for the baseline plans.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
