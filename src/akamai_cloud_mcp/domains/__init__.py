"""Domain registry: domain name -> register(mcp, ctx) function.

`build_server` calls only the register functions for selected domains, so an
unselected domain registers zero tools. This conditional registration is the
primary, version-proof anti-bloat control (it works identically on FastMCP 2.x
and 3.0, with no dependence on the tag-filtering API).

Each domain module exposes `register(mcp, ctx)`. Modules are imported lazily
inside `get_registrars` so importing the package never forces every domain
module to import its SDK dependencies.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from akamai_cloud_mcp.context import ServerContext

Registrar = Callable[[Any, ServerContext], None]


def get_registrars() -> dict[str, Registrar]:
    """Return the domain-name -> register-function map."""
    from akamai_cloud_mcp.domains import (
        account_billing,
        compute,
        databases,
        dns,
        escape_hatch,
        lke,
        networking,
        object_storage,
        pricing,
        regions_catalog,
    )

    return {
        "regions": regions_catalog.register,
        "pricing": pricing.register,
        "compute": compute.register,
        "lke": lke.register,
        "object_storage": object_storage.register,
        "networking": networking.register,
        "account": account_billing.register,
        "dns": dns.register,
        "databases": databases.register,
        "escape": escape_hatch.register,
    }
