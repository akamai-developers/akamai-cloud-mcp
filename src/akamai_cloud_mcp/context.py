"""Shared context passed to every domain's register() function."""

from __future__ import annotations

from dataclasses import dataclass

from akamai_cloud_mcp.client import LinodeClientWrapper
from akamai_cloud_mcp.config import Config


@dataclass
class ServerContext:
    """Everything a domain module needs to register and back its tools."""

    config: Config
    client: LinodeClientWrapper
