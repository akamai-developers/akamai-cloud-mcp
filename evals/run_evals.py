#!/usr/bin/env python
"""Agent eval harness for akamai-cloud-mcp.

Runs realistic solutions-architect tasks through a headless Claude Code agent
against the live server and scores tool selection + answer sanity. This is the
repeatable way to validate tool naming/descriptions (Anthropic: evaluate tools
with real agents), not a unit test -- it spends tokens and hits the live API.

Each task (evals/tasks.json) declares:
  - prompt:        the user request
  - must_use_any:  the agent must call at least one of these tools (the core
                   tool-selection check)
  - expect_regex:  the final answer must match this (a light sanity check)
  - needs_token:   skip unless LINODE_TOKEN is set

Usage:
    uv run python evals/run_evals.py                 # all tasks
    uv run python evals/run_evals.py --task regions_list
Requires the `claude` CLI and network access to api.linode.com.
Exit code is non-zero if any non-skipped task fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER_NAME = "akamai-cloud"


def tool_ids() -> list[str]:
    """Full mcp tool ids to allowlist for the headless agent."""
    from fastmcp.client import Client

    from akamai_cloud_mcp.server import build_server

    async def _names() -> list[str]:
        async with Client(build_server(domains="all")) as c:
            return [t.name for t in await c.list_tools()]

    return [f"mcp__{SERVER_NAME}__{n}" for n in asyncio.run(_names())]


def write_mcp_config(path: Path) -> Path:
    cfg = {
        "mcpServers": {
            SERVER_NAME: {
                "command": "uv",
                "args": ["run", "--project", str(ROOT), "akamai-cloud-mcp"],
            }
        }
    }
    path.write_text(json.dumps(cfg))
    return path


def run_task(prompt: str, cfg: Path, allowed: list[str]) -> tuple[list[str], str, int]:
    cmd = [
        "claude", "-p", prompt,
        "--mcp-config", str(cfg),
        "--allowedTools", ",".join(allowed),
        "--output-format", "stream-json", "--verbose",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    tools_used: list[str] = []
    answer, tokens = "", 0
    for line in proc.stdout.splitlines():
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("type") == "assistant":
            for blk in o.get("message", {}).get("content", []):
                if isinstance(blk, dict) and blk.get("type") == "tool_use":
                    tools_used.append(blk.get("name", ""))
        elif o.get("type") == "result":
            answer = o.get("result", "") or ""
            usage = o.get("usage", {}) or {}
            tokens = (usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0)
    return tools_used, answer, tokens


def score(task: dict, tools_used: list[str], answer: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    # Captured names are full mcp ids (mcp__server__linode_x); compare short names.
    used = {t.split("__")[-1] for t in tools_used}
    must_any = task.get("must_use_any")
    if must_any and not (used & set(must_any)):
        reasons.append(f"used none of {must_any}")
    rx = task.get("expect_regex")
    if rx and not re.search(rx, answer, re.I):
        reasons.append(f"answer did not match /{rx}/")
    return (not reasons), reasons


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", help="run only this task id")
    args = ap.parse_args()

    if not shutil.which("claude"):
        sys.exit("error: the `claude` CLI is required but was not found on PATH.")

    tasks = json.loads((Path(__file__).parent / "tasks.json").read_text())
    have_token = bool(os.environ.get("LINODE_TOKEN") or os.environ.get("LINODE_API_TOKEN"))
    allowed = tool_ids()

    rows: list[tuple] = []
    npass = nrun = total_tokens = total_calls = 0
    with tempfile.TemporaryDirectory() as d:
        cfg = write_mcp_config(Path(d) / "mcp.json")
        for task in tasks:
            if args.task and task["id"] != args.task:
                continue
            if task.get("needs_token") and not have_token:
                rows.append((task["id"], "SKIP", 0, 0, "no LINODE_TOKEN"))
                continue
            tools_used, answer, tokens = run_task(task["prompt"], cfg, allowed)
            ok, reasons = score(task, tools_used, answer)
            nrun += 1
            npass += int(ok)
            total_tokens += tokens
            total_calls += len(tools_used)
            short = ",".join(t.split("__")[-1] for t in tools_used)
            detail = "; ".join(reasons) if reasons else short
            rows.append((task["id"], "PASS" if ok else "FAIL", len(tools_used), tokens, detail))

    print(f"\n{'task':18} {'result':6} {'calls':>5} {'tokens':>7}  detail")
    print("-" * 72)
    for tid, res, calls, toks, detail in rows:
        print(f"{tid:18} {res:6} {calls:>5} {toks:>7}  {detail}")
    print("-" * 72)
    print(f"{npass}/{nrun} passed | {total_calls} tool calls | {total_tokens} tokens")
    sys.exit(0 if npass == nrun else 1)


if __name__ == "__main__":
    main()
