# Contributing

Thanks for helping improve the Akamai Cloud MCP server. This is a read-only,
safety-first server. Keep it that way.

## Dev setup

This project uses [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/akamai-developers/akamai-cloud-mcp
cd akamai-cloud-mcp
uv sync
```

Run the checks:

```bash
uv run pytest -q        # tests run against a mocked Linode API, no credentials
uv run ruff check .
uv run mypy
```

The full suite makes zero live Linode calls. The SDK is mocked at its
synchronous boundary. Never add a test that needs a real token.

## Adding a domain or tool

- Tools live in `src/akamai_cloud_mcp/domains/<domain>.py`. Each module exposes
  `register(mcp, ctx)`.
- New domains are added to the registry in `domains/__init__.py` and to
  `ALL_DOMAINS` in `config.py`.
- Every tool is read-only, annotated `readOnlyHint: true`, builds its result
  with an allowlist serializer (`serialize.pick`), and returns it through
  `scrub()`.
- Cap `list_*` results with `ctx.config.max_results` and say in the response when
  results were capped.

## Anti-bloat rule

The curated tool set stays in the low tens. Do not add a tool per endpoint. Push
the long tail to the `linode_api_get` escape hatch. If a request needs a new
curated tool, it should answer a real, common question that the escape hatch
cannot answer well.

## Read-only rule

No write or mutating operation, anywhere. No non-GET HTTP verb. No mutating SDK
method. The static read-only scan and the HTTP-verb guard in the test suite will
fail your change if you break this.

## Writing style

Docs and comments are developer-to-developer and tactical. Hard rules:

- No em-dashes anywhere.
- No AI filler ("delve", "in today's fast-paced", "it's worth noting",
  "seamless", "robust", "leverage" as a verb).

## Licensing note

This server is licensed Apache-2.0 by choice. The Linode SDK it depends on is
BSD-3-Clause. Contributions are accepted under the project's Apache-2.0 license.
