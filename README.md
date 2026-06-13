# Akamai Cloud MCP

mcp-name: io.github.akamai-developers/akamai-cloud-mcp

A read-only [Model Context Protocol](https://modelcontextprotocol.io) server for
Akamai Cloud (Linode). Point an MCP client (Claude Desktop, Claude Code, Cursor,
or any MCP client) at it, give it a read-only-scoped Linode token, and ask
natural-language questions about your account: what you run, what a stack would
cost, where GPUs are in stock, and which account limits apply.

This is one general server, not a fleet of per-service servers. Akamai Cloud is a
single cohesive API, so the right shape is one curated server with domain modules
inside, similar to AWS's general API MCP server rather than its per-service fleet.
The active tool set stays in the low tens.

## Status

Early development. v1 is read-only and ships no write or mutating operations.

## Design

- **Read-only.** No write or mutating operation anywhere in v1. Enforced by a
  GET-only client, a static code scan, and an HTTP-verb guard in the tests.
- **Curated, not auto-generated.** A focused tool set tuned for LLM tool
  selection, plus one generic read-only escape hatch (`linode_api_get`) for the
  long tail. No tool-per-endpoint sprawl.
- **Safety first.** A scoped token read from the environment, never logged.
  Secrets (LKE kubeconfigs, Object Storage keys, tokens, payment and PII fields)
  are removed from results by allowlist serialization and a recursive scrub.
- **Domain toggles.** Load only the domain groups you want with `--domains`.
- **Dual transport.** stdio for local clients, streamable-HTTP for hosted use.

## Domains and tools

All tools are read-only. Load a subset with `--domains compute,pricing`.

| Domain | Tools |
|---|---|
| `regions` | `list_regions`, `get_region_availability`, `list_instance_types` |
| `pricing` | `get_pricing`, `find_gpu_availability`, `estimate_cost` |
| `compute` | `list_instances`, `get_instance`, `list_volumes` |
| `lke` | `list_lke_clusters`, `get_lke_cluster`, `list_kubernetes_versions` |
| `object_storage` | `list_object_storage_buckets`, `list_object_storage_endpoints`, `get_object_storage_transfer`, `list_object_storage_quotas` |
| `networking` | `list_firewalls`, `list_ips`, `list_vlans`, `list_vpcs`, `get_vpc`, `list_nodebalancers` |
| `account` | `get_account`, `get_account_transfer`, `list_invoices`, `list_events`, `get_account_limits` |
| `escape` | `linode_api_get` |

The tool implementations land across the build phases. The table is the target
surface.

## Install

The documented install paths are `uvx` and `pipx` (available once published to
PyPI). For local development:

```bash
uv sync
uv run akamai-cloud-mcp --help
```

## Token setup

Create a Linode personal access token with read-only scopes and export it:

```bash
export LINODE_TOKEN="<your-linode-token>"
```

`LINODE_API_TOKEN` is accepted as an alias. Recommended scopes are read-only:
`linodes:read_only`, `lke:read_only`, `object_storage:read_only`,
`account:read_only`, `events:read_only`, and the rest as needed. The server never
logs or echoes the token.

## Pricing

Pricing uses the public type and price endpoints, so catalog questions work even
without a token. Two details the tools get right so you do not have to:

- **Region price fallback.** A type's top-level `price` is the default-region
  price. `region_prices[]` lists overrides for the few higher-cost regions
  (currently Jakarta and Sao Paulo). To price a region, the tool matches the
  region id in `region_prices[]` and falls back to the default price when there
  is no override.
- **Null monthly means metered.** Metered SKUs (network transfer, Object Storage
  overage) report `monthly` as null, not 0. Null means priced per unit with no
  monthly cap. The tools never coerce null to 0.

Some costs are invisible to the API (Object Storage Class A/B request pricing,
free-allotment thresholds, policy facts like no egress fees to Akamai CDN). Those
live in a curated in-repo supplement, each entry carrying a source and a review
date. `get_pricing` for the `object_storage` family returns that supplement
alongside the live storage price.

## Worked example: estimate_cost

`estimate_cost` composes a stack from live prices plus the curated supplement.
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

## find_gpu_availability

`find_gpu_availability` returns both the `gpu` class (NVIDIA RTX plans, `gpus >
0`) and the `accelerated` class (for example NETINT VPU plans,
`accelerated_devices > 0` and `gpus == 0`), each with price and the regions where
it is in stock. Pass a region to scope it. Marketing-only SKUs that are not
self-serve priced (for example RTX PRO 6000 Blackwell, "by request") are listed
separately so they are visible without being treated as orderable.

## Inventory

The `compute` domain answers what you run: `list_instances` and `get_instance`
return region, type, status, IPs, image, and specs; `list_volumes` returns block
storage with the instance each volume is attached to. Results are allowlist
serialized (only safe fields leave the SDK) and capped at `--max-results`.

## Read-only and scrubbing guarantees

- Every tool is annotated `readOnlyHint: true`.
- The client issues GET only. A static scan and an HTTP-verb guard in the test
  suite fail the build if a mutating call is introduced.
- Tools return allowlist-serialized dicts, then run through a recursive scrub.
  Kubeconfigs, access and secret keys, tokens, and payment or PII fields never
  reach the model.
- The escape hatch denylists known secret endpoints outright.

See [SECURITY.md](SECURITY.md) for the full posture.

## License

[Apache-2.0](LICENSE).
