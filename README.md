# Akamai Cloud MCP Server

[![CI](https://github.com/akamai-developers/akamai-cloud-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/akamai-developers/akamai-cloud-mcp/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

A read-only [Model Context Protocol](https://modelcontextprotocol.io) server for
Akamai Cloud (Linode). Point any MCP client or agent at it, give it a
read-only-scoped Linode token, and ask plain-language questions about your
account: what you run, what a stack would cost, where GPUs are in stock, and
which account limits apply.

It is one curated server, not a fleet of per-service servers: Akamai Cloud is a
single cohesive API, so the tools live in one server with domain modules inside.

## Features

- **Inventory** - list compute instances, block-storage volumes, LKE clusters,
  Object Storage buckets, firewalls, IPs, VLANs, VPCs, and NodeBalancers, with
  the details that matter (region, type, status, attachments) and nothing that
  leaks.
- **Pricing and cost estimates** - live per-type pricing with the correct
  region-override fallback, GPU and accelerated-plan availability by region, and
  full-stack monthly estimates that itemize every line and label its source.
- **Account and limits** - account details, network transfer, invoices, the
  event log, and a composed account-limits summary. Payment and PII fields are
  redacted on every return.
- **Read-only by construction** - a GET-only client, allowlist serialization,
  and a recursive secret scrub. Enforced by a static scan and a runtime
  HTTP-verb guard, not just convention.
- **Curated, low-context surface** - 37 tools tuned for tool selection, plus one
  read-only escape hatch (`linode_api_get`) for the long tail. No
  tool-per-endpoint sprawl. Load only the domains you need with `--domains`.
- **Dual transport** - `stdio` for local clients, auth-gated `streamable-http`
  for hosted deployments.

## Prerequisites

1. Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) (it
   provides `uvx`, used to run the server). `pipx` works too.
2. Python 3.11 or newer.
3. A Linode personal access token with **read-only** scopes (see
   [Token setup](#token-setup)). Pricing and catalog tools work without a token;
   account-scoped tools require one.

## Installation

Run straight from PyPI with no install step:

```bash
uvx akamai-cloud-mcp --help
```

Or install it onto your PATH:

```bash
pipx install akamai-cloud-mcp
```

## Client configuration

Add the server to your MCP client and pass your token in the `env` block.
Anything after the package name in `args` is passed to the server, so this is
where you scope domains, cap results, or change transport. See
[Arguments](#arguments) for the full list.

### Claude Desktop

Open **Settings → Developer → Edit Config** and add the server to
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "akamai-cloud": {
      "command": "uvx",
      "args": ["akamai-cloud-mcp"],
      "env": {
        "LINODE_TOKEN": "<your-read-only-linode-token>"
      }
    }
  }
}
```

### Claude Code

Add it with one command:

```bash
claude mcp add akamai-cloud --env LINODE_TOKEN=<your-read-only-linode-token> -- uvx akamai-cloud-mcp
```

Or commit a project-scoped `.mcp.json` so your agents share the same config.
This example loads only the `compute`, `pricing`, and `regions` domains and
raises the result cap:

```json
{
  "mcpServers": {
    "akamai-cloud": {
      "command": "uvx",
      "args": [
        "akamai-cloud-mcp",
        "--domains", "compute,pricing,regions",
        "--max-results", "100"
      ],
      "env": {
        "LINODE_TOKEN": "<your-read-only-linode-token>"
      }
    }
  }
}
```

### Cursor

Add the server to `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (per
project). This example narrows the surface to inventory and cost tools:

```json
{
  "mcpServers": {
    "akamai-cloud": {
      "command": "uvx",
      "args": [
        "akamai-cloud-mcp",
        "--domains", "compute,pricing"
      ],
      "env": {
        "LINODE_TOKEN": "<your-read-only-linode-token>"
      }
    }
  }
}
```

Any MCP client that launches a `command` works the same way: `command` is `uvx`,
`args` starts with `akamai-cloud-mcp`, and the token goes in `env`.

## Arguments

Pass these after `akamai-cloud-mcp` in `args` (CLI flags override environment
variables).

| Argument | Environment variable | Default | Description |
|---|---|---|---|
| `--domains <list\|all>` | `AKAMAI_MCP_DOMAINS` | `all` | Comma-separated domains to load. Choices: `regions`, `pricing`, `compute`, `lke`, `object_storage`, `networking`, `account`, `dns`, `databases`, `escape`. |
| `--max-results <int>` | `AKAMAI_MCP_MAX_RESULTS` | `50` | Cap on rows returned by `list_*` tools, so a tool never floods model context. |
| `--transport <name>` | `AKAMAI_MCP_TRANSPORT` | `stdio` | `stdio`, `streamable-http`, or `http` (alias for `streamable-http`). |
| `--host <host>` | `AKAMAI_MCP_HOST` | `127.0.0.1` | Bind host for the HTTP transport. |
| `--port <int>` | `AKAMAI_MCP_PORT` | `8080` | Bind port for the HTTP transport. |
| `--path <path>` | `AKAMAI_MCP_PATH` | `/mcp` | URL path for the HTTP transport. |
| `--version` | - | - | Print the version and exit. |

Secrets are read from the environment, never from CLI flags:

| Environment variable | Required | Description |
|---|---|---|
| `LINODE_TOKEN` | For account-scoped tools | Read-only-scoped Linode personal access token. `LINODE_API_TOKEN` is accepted as an alias. |
| `AKAMAI_MCP_HTTP_AUTH_TOKEN` | For HTTP transport | Bearer token that HTTP clients must present. The HTTP transport refuses to start without it. |

## Token setup

Create a Linode personal access token with read-only scopes and export it:

```bash
export LINODE_TOKEN="<your-read-only-linode-token>"
```

The default tool set spans several services, so grant all of these read-only
scopes (this is the set the server recommends):

`linodes:read_only`, `lke:read_only`, `object_storage:read_only`,
`nodebalancers:read_only`, `firewall:read_only`, `vpc:read_only`,
`ips:read_only`, `account:read_only`, `events:read_only`.

If you load only a subset of domains with `--domains`, you only need the scopes
for those services. The server never logs or echoes the token, and
`LINODE_API_TOKEN` is accepted as an alias.

## Usage

With the server configured, ask your client natural-language questions:

- "List my running Linodes and which region each is in."
- "What would 3x g6-standard-2 with backups, a 200 GB volume, and an HA LKE control plane cost per month in us-east?"
- "Where can I get an RTX GPU plan right now?"
- "Show my Object Storage buckets and this period's transfer usage."
- "What are my account limits?"

## Tools

All tools are read-only and annotated `readOnlyHint: true`. Load a subset with
`--domains`.

### `regions`

| Tool | Signature | Description |
|---|---|---|
| `linode_list_regions` | `()` | Regions with capabilities, country, site type, and status. |
| `linode_get_region_availability` | `(region?: str)` | Which plans are in stock, account-wide or scoped to one region. |
| `linode_list_instance_types` | `()` | Plan types with vcpus, memory, disk, transfer, GPUs, class, and prices. |

### `pricing`

| Tool | Signature | Description |
|---|---|---|
| `linode_get_pricing` | `(family: str, region?: str)` | Per-type pricing for a family (`compute`, `block_storage`, `nodebalancers`, `network_transfer`, `lke`, `object_storage`) with the correct region override applied. |
| `linode_find_gpu_availability` | `(region?: str)` | GPU and accelerated plans with price and the regions where each is in stock. |
| `linode_estimate_cost` | `(request: EstimateRequest)` | Itemized hourly and monthly cost of a described stack, each line labeled by source. |

### `compute`

| Tool | Signature | Description |
|---|---|---|
| `linode_list_instances` | `()` | Compute instances with region, type, status, IPs, image, and specs. |
| `linode_get_instance` | `(instance_id: int)` | One instance by id. |
| `linode_list_volumes` | `()` | Block-storage volumes with size, region, status, and attachment. |

### `lke`

| Tool | Signature | Description |
|---|---|---|
| `linode_list_lke_clusters` | `()` | LKE clusters with region, Kubernetes version, tier, and control-plane settings. |
| `linode_get_lke_cluster` | `(cluster_id: int)` | One cluster with node pools, API endpoints, and control-plane ACL. The kubeconfig is never returned. |
| `linode_list_kubernetes_versions` | `()` | Kubernetes versions available for new and upgraded clusters. |

### `object_storage`

| Tool | Signature | Description |
|---|---|---|
| `linode_list_object_storage_buckets` | `(region?: str)` | Buckets with hostname, endpoint type, size, and object count. Keys are never returned. |
| `linode_get_object_storage_bucket` | `(region: str, bucket: str)` | One bucket's detail (hostname, S3 endpoint, size, object count). Keys are never returned. |
| `linode_list_object_storage_endpoints` | `()` | Endpoints (region, type, S3 hostname) available to the account. |
| `linode_get_object_storage_transfer` | `()` | Object Storage network transfer for the current billing period. |
| `linode_list_object_storage_quotas` | `()` | Object Storage quotas (the only quota API Linode exposes). |

### `networking`

| Tool | Signature | Description |
|---|---|---|
| `linode_list_firewalls` | `()` | Cloud Firewalls with status and tags. Use `linode_get_firewall` for rules. |
| `linode_get_firewall` | `(firewall_id: int)` | One firewall with its inbound/outbound rules and attached resources. |
| `linode_list_ips` | `()` | IP addresses with type, region, reverse DNS, and assignment. |
| `linode_list_vlans` | `()` | VLANs with region, CIDR, and attached instances. |
| `linode_list_vpcs` | `()` | VPCs with region and description. |
| `linode_get_vpc` | `(vpc_id: int)` | One VPC with its subnets and the instances in each. |
| `linode_list_nodebalancers` | `()` | NodeBalancers with region, hostname, IPs, and transfer usage. |

### `account` (on by default)

| Tool | Signature | Description |
|---|---|---|
| `linode_get_account` | `()` | Company, country, balance, capabilities. Payment and personal fields redacted. |
| `linode_get_account_transfer` | `()` | Network transfer for the current billing period, including per-region. |
| `linode_list_invoices` | `()` | Invoices with date, subtotal, tax, and total. Payment detail redacted. |
| `linode_list_events` | `()` | Recent account events (the audit log). |
| `linode_get_account_limits` | `()` | Composed account-limits summary (rate limits, Object Storage quotas, transfer pool). |

Leave `account` out of `--domains` if you do not want account data in the
model's context.

### `dns`

| Tool | Signature | Description |
|---|---|---|
| `linode_list_domains` | `()` | DNS domains (zones) with type, status, and SOA email. |
| `linode_get_domain` | `(domain_id: int)` | One zone with SOA timers, master/AXFR IPs, and tags. |
| `linode_list_domain_records` | `(domain_id: int)` | A/AAAA/NS/MX/CNAME/TXT/SRV/PTR/CAA records with name, target, and TTL. |

### `databases`

| Tool | Signature | Description |
|---|---|---|
| `linode_list_databases` | `()` | Managed Database clusters (all engines) with engine, version, region, status, plan, and host. Credentials never returned. |
| `linode_get_database` | `(engine: str, database_id: int)` | One database by engine (`mysql`/`postgresql`) and id, with host, port, and maintenance window. Root password never returned. |
| `linode_list_database_engines` | `()` | Available database engines and versions. |
| `linode_list_database_types` | `()` | Managed Database plan types with vcpus, memory, disk, engines, and price. |

### `escape`

| Tool | Signature | Description |
|---|---|---|
| `linode_api_get` | `(path: str, params?: dict)` | Read-only GET against any Linode API v4 path a curated tool does not cover, for example `/images` or `/tags`. |

The escape hatch is defended in depth: only GET is allowed, the path is
validated (relative v4 only, no absolute URL, no traversal), known
secret-returning endpoints (kubeconfig, Object Storage keys, profile tokens,
payment methods) are refused outright, and the response is scrubbed. It is why
there is no tool-per-endpoint sprawl.

## Worked example: `linode_estimate_cost`

`linode_estimate_cost` composes a stack from live prices plus the curated supplement.
Given this request:

```json
{
  "region": "us-east",
  "instances": [{"type": "g6-standard-1", "count": 1, "backups": true}],
  "volumes": [{"size_gb": 100, "count": 1}],
  "nodebalancers": 1,
  "lke_tier": "ha",
  "object_storage": {
    "storage_gb": 500,
    "class_a_requests": 2000000,
    "class_b_requests": 12500000,
    "egress_gb": 0
  }
}
```

it returns itemized lines, each labeled by source, with free allotments applied
before overage:

| Line | Source | Monthly |
|---|---|---|
| 1x g6-standard-1 | live API | 10.00 |
| backups for 1x g6-standard-1 | live API | 2.50 |
| 1x 100GB block storage | live API | 10.00 |
| 1x NodeBalancer | live API | 10.00 |
| LKE ha control plane | live API | 60.00 |
| 500GB stored (250GB included) | curated supplement | 5.00 |
| 2,000,000 class A requests (1,000,000 free) | curated supplement | 5.00 |
| 12,500,000 class B requests (12,500,000 free) | curated supplement | 0.00 |

Total: 102.50/month. The class B requests sit exactly at the free quota, so they
add nothing. LKE worker nodes are priced as their underlying instance types, so
add them under `instances`. These figures match the golden-output test, so the
example and the tool cannot drift apart.

## Pricing notes

Pricing uses the public type and price endpoints, so catalog questions work even
without a token. Two details the tools get right so you do not have to:

- **Region price fallback.** A type's top-level `price` is the default-region
  price; `region_prices[]` lists overrides for the few higher-cost regions
  (currently Jakarta and Sao Paulo). To price a region, the tool matches the
  region id in `region_prices[]` and falls back to the default when there is no
  override.
- **Null monthly means metered.** Metered SKUs (network transfer, Object Storage
  overage) report `monthly` as `null`, not `0`. Null means priced per unit with
  no monthly cap. The tools never coerce null to 0.

Some costs are invisible to the API (Object Storage Class A/B request pricing,
free-allotment thresholds, policy facts like no egress fees to Akamai CDN).
Those live in a curated in-repo supplement, each entry carrying a source and a
review date. `linode_get_pricing` for the `object_storage` family returns that
supplement alongside the live storage price.

## Context cost

Tool definitions count against your model's context window, so this server keeps
that small on purpose. Approximate footprint (measured with a GPT tokenizer;
Claude is within about 10 percent):

| Domains loaded | Tools | Tokens (approx) |
|---|---|---|
| all (default) | 37 | ~3,440 |
| `compute,lke,regions` | 9 | ~710 |
| `pricing` | 3 | ~760 |
| `databases` | 4 | ~310 |
| `dns` | 3 | ~270 |
| `compute` | 3 | ~220 |

Load a subset to shrink the footprint, for example
`--domains compute,pricing` when you only need inventory and cost.

## HTTP deployment

For a hosted deployment, run the `streamable-http` transport:

```bash
export LINODE_TOKEN="<your-read-only-linode-token>"
export AKAMAI_MCP_HTTP_AUTH_TOKEN="<a-bearer-token-clients-must-present>"
akamai-cloud-mcp --transport streamable-http --host 0.0.0.0 --port 8080 --path /mcp
```

The server is served at `/mcp/`.

> [!WARNING]
> The HTTP transport uses **one shared server-side `LINODE_TOKEN`**. Every
> authenticated caller queries the **same** Linode account. This is not a
> bring-your-own-token design - do not expose one account's data to a shared
> audience by accident. The transport refuses to start without
> `AKAMAI_MCP_HTTP_AUTH_TOKEN` (set `AKAMAI_MCP_ALLOW_INSECURE_HTTP=1` to
> override, which is strongly discouraged). Always run it behind TLS.

## Read-only and scrubbing guarantees

- Every tool is annotated `readOnlyHint: true`.
- The client issues GET only. A static scan and an HTTP-verb guard in the test
  suite fail the build if a mutating call is introduced.
- Curated tools return allowlist-serialized dicts - only known-safe fields leave
  the SDK - then run through a recursive scrub. Kubeconfigs, access and secret
  keys, tokens, and payment and PII fields do not reach the model on these paths.
- The escape hatch (`linode_api_get`) returns raw API objects passed through the
  scrub only, and refuses a denylist of known secret-returning endpoints. The
  scrub strips known secret material (kubeconfigs, keys, tokens), but a raw
  account endpoint can still surface account PII - keep the token
  read-only-scoped and prefer the curated `account` tools for account data.

See [SECURITY.md](SECURITY.md) for the full posture.

## Development

```bash
uv sync
uv run akamai-cloud-mcp --help
```

Run the checks the way CI does:

```bash
uv run pytest -q       # mocked Linode API, zero live calls
uv run ruff check .
uv run mypy
```

CI runs ruff, mypy, and pytest on Python 3.11 and 3.12 (read-only enforcement is
covered by the static scan and verb-guard tests, described under
[Read-only and scrubbing guarantees](#read-only-and-scrubbing-guarantees)). A
separate scheduled job (`pricing-staleness.yml`) flags price drift against
`scripts/pricing_baseline.json` using the public type endpoints, so it needs no
credentials.

To build and run the wheel locally:

```bash
uv build
uvx --from ./dist/akamai_cloud_mcp-*.whl akamai-cloud-mcp --help
```

## Status

v0.1.0. v1 is read-only and ships no write or mutating operations. See
[CHANGELOG.md](CHANGELOG.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The bar is the CI gates above plus the
read-only rule: no tool may issue a non-GET request.

## License

[Apache-2.0](LICENSE).
