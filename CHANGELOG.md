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
