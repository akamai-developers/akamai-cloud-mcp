# Evals

A small agent-evaluation harness. It runs realistic solutions-architect tasks
through a headless Claude Code agent against the live server and scores **tool
selection** (did the agent call the right tool?) and **answer sanity**. This is
the repeatable way to validate tool naming and descriptions and to catch
selection regressions -- it is not a unit test (it spends tokens and hits the
live Linode API).

## Run

```bash
# all tasks (account tasks are skipped unless LINODE_TOKEN is set)
uv run python evals/run_evals.py

# one task
uv run python evals/run_evals.py --task regions_list
```

Requires the `claude` CLI and network access to `api.linode.com`. Catalog and
pricing tasks need no token; account tasks (`needs_token: true`) are skipped
without `LINODE_TOKEN`.

## What it measures

Per task: pass/fail, number of tool calls, and tokens consumed. Aggregate: pass
rate, total tool calls, total tokens. The harness exits non-zero if any
non-skipped task fails, so it can gate a release manually.

## Add a task

Append to `tasks.json`:

```json
{
  "id": "short_id",
  "prompt": "Using only the akamai-cloud MCP tools, ...",
  "must_use_any": ["linode_some_tool"],
  "expect_regex": "pattern the final answer should contain",
  "needs_token": false
}
```

Keep tasks grounded in real questions a solutions architect would ask, and lean
on `must_use_any` to assert the agent picks the intended tool. When a task
exposes a tool the agent *should* have used but didn't, that is a signal to
sharpen the tool's description or naming -- exactly what this harness is for.
