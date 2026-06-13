# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project foundation: `uv`-managed package, `pyproject.toml` with metadata and
  the `akamai-cloud-mcp` console script.
- `build_server(domains=...)` with conditional domain registration: only the
  selected domain groups register tools.
- CLI (`run`) parsing `--transport`, `--host`, `--port`, `--path`, `--domains`,
  `--max-results`, and a disabled `--allow-write` seam.
- `config.py`, `auth.py` (token load and a warn-only, scrubbed scope check),
  `client.py` (synchronous SDK wrapper, httpx fallback, 24h price cache),
  `serialize.py` (allowlist serializers), `scrub.py` (recursive redaction),
  `errors.py` (clean error mapping), and the curated pricing supplement loader.
- Read-only domain module scaffolding for all v1 domains.
- `ruff` and `mypy` configuration; scrub and server-construction tests.
- Regions & Catalog tools: `list_regions`, `get_region_availability` (account-wide
  and per-region), `list_instance_types`.
- Pricing tool `get_pricing` for compute, block storage, NodeBalancers, network
  transfer, LKE control plane, and Object Storage, with region price fallback and
  null-monthly handling. Object Storage results include the curated request
  pricing supplement.
- Curated pricing supplement data: Object Storage Class A/B request rates and
  free quotas, free-allotment thresholds, and policy facts.
- `find_gpu_availability`: returns gpu and accelerated plans with prices and the
  regions where each is in stock; flags marketing-only SKUs separately.
- `estimate_cost`: composed hourly and monthly estimate of a described stack
  (instances with backups, volumes, NodeBalancers, LKE control-plane tier, and
  Object Storage usage), with itemized source-labeled lines, explicit
  assumptions, and free allotments applied before overage. Pinned input model.
- Pricing staleness diff plus a golden-output test for the worked example.
- Supplement additions: Object Storage storage overage rate and network transfer
  overage rate.
- Compute tools: `list_instances`, `get_instance`, `list_volumes`, allowlist
  serialized and result-capped.
- LKE tools: `list_lke_clusters`, `get_lke_cluster` (composes node pools, API
  endpoints, control plane ACL, and dashboard URL), `list_kubernetes_versions`.
  The kubeconfig is never read or returned.
- Object Storage tools: `list_object_storage_buckets`,
  `list_object_storage_endpoints`, `get_object_storage_transfer`,
  `list_object_storage_quotas`. Access and secret keys are never returned and
  there is no key-listing tool.
- Networking tools: `list_firewalls`, `list_ips`, `list_vlans`, `list_vpcs`,
  `get_vpc` (with subnets), `list_nodebalancers`.
- Account & Billing tools: `get_account` (PII and payment fields redacted),
  `get_account_transfer`, `list_invoices`, `list_events`, and the composed
  `get_account_limits`, which is honest that Linode exposes no single per-account
  service-limit endpoint. The domain can be toggled off with `--domains`.
