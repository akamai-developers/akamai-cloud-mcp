# Security

This server is built to be safe to point at a real Akamai Cloud (Linode)
account. The guarantees below are enforced in code and tested.

## Read-only posture (v1)

v1 performs no write or mutating operations. Read-only is enforced structurally,
not by a runtime promise:

- `client.py` only ever issues GET. No `post`, `put`, `delete`, or `patch` verb,
  and no mutating SDK method (create, update, delete, save, invalidate) is called
  anywhere in `src/`.
- The escape-hatch tool hardcodes the HTTP method to GET and rejects anything
  else.
- A static test scans `src/` for mutating method names and non-GET verbs and
  fails if any appear. A second test monkeypatches the HTTP verbs to raise during
  the suite, so an accidental mutating call breaks the tests.
- Every tool is annotated `readOnlyHint: true` for clients.

A future write capability would land behind an explicit, tiered opt-in flag. The
`--allow-write` flag exists today as a disabled seam and gates nothing.

## Scoped token, never logged

The server reads a Linode personal access token from `LINODE_TOKEN` (or the
documented alias `LINODE_API_TOKEN`). Use a read-only-scoped token. The token is
passed only to the Linode client. It is never logged, echoed, or returned in any
response or error message.

## Response scrubbing

Secrets are removed with defense in depth:

1. Allowlist serialization is the primary control. Each tool copies only named
   safe fields out of the SDK object. Secret-bearing attributes (kubeconfigs,
   key material, tokens, payment methods) are never read.
2. A recursive scrub runs on every tool return as a backstop, redacting by key
   name (kubeconfig, secret, token, password, key material, payment and PII
   fields) and by value shape (PEM blocks, base64 kubeconfigs, JWTs,
   bearer-prefixed values, high-entropy secret-shaped strings).
3. Log lines are scrubbed too.

The LKE tools never read or return a cluster kubeconfig. The Object Storage tools
never return access or secret keys, and there is no key-listing tool.

## Escape-hatch path denylist

The generic `linode_api_get` tool refuses known secret-returning endpoints
outright, before any response is even fetched: cluster kubeconfig paths, Object
Storage keys, profile tokens, and account payment methods. It validates the path
(relative v4 only, no host override, no traversal) and scrubs the result.

## HTTP transport

The HTTP transport uses one shared server-side `LINODE_TOKEN`. Every
authenticated caller queries the same Linode account. This is not a
bring-your-own-token design. The transport requires a bearer token verifier or
refuses to start, and should run behind TLS. See the README HTTP deploy section.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to the maintainer rather than
opening a public issue. Open a GitHub security advisory on the repository, or
email the maintainer listed in `pyproject.toml`. We will acknowledge receipt and
work on a fix before public disclosure.
