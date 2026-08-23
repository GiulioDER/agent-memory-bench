"""Phase 2 pilot: bare vs claude_md vs recall over the full task grid. A MEASUREMENT.

Refuses to start while `preregistration/` is dirty; the committed record for this run is
`preregistration/000-pilot.md`. Everything the pilot exists to produce is written there:
task screening (ceiling and floor), variance for the power analysis, and the mechanism
metrics (search rate, governing-session-reached rate) beside the outcome.

Per-task system prompts: the `claude_md` arm receives the fixture's own README as its static
bundle (the hand-maintained knowledge a real project carries); the `recall` arm receives the
identical bundle with the one-line tool instruction at the TOP (the buried-instruction
lesson); `bare` receives nothing. The governing facts are verifiably absent from bundles and
fixtures (`scripts/audit_corpus.py` locus check), so the only route to them is memory.

    python -m scripts.pilot --run-id pilot-001

Environment: OPENROUTER_API_KEY; RECALL_DSN pointing at the bench database whose
`bench-recall-pilot` tenant holds the ingested corpus; PYTHONPATH pinned to the recall
checkout that serves the MCP server (the shared editable install resolves `recall` from an
arbitrary worktree otherwise, which is a measured hazard).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness import sandbox
from harness.claude_exec import ClaudeExecConfig, run_claude_case
from harness.costs import ModelPricing, summarize
from harness.gate import AdmissionSignal, admit_cells, with_forbidden_prefixes
from harness.io import write_jsonl
from harness.prereg import assert_preregistered
from harness.runner import run_grid
from harness.tasks import discover_tasks, run_checker

ARMS = ("bare", "claude_md", "recall")
BASE_TOOLS = ("Read", "Grep", "Glob", "Bash", "Write", "Edit")
DENIED_TOOLS = ("Bash(docker:*)", "Bash(docker-compose:*)")
RECALL_CONFIG = json.loads(
    (REPO / "adapters" / "recall" / "config.frozen.json").read_text(encoding="utf-8")
)
RECALL_PREFIX = str(RECALL_CONFIG["tool_prefix"])
GENERIC_RULES = (
    "# Project notes\n\n"
    "You are working in this repository. Keep changes small and leave the tree clean.\n\n"
)


def build_bundles(task, out_dir: Path) -> dict[str, Path]:
    """Per-task static bundles: identical bytes for claude_md and the tail of recall's."""

    readme = task.path / "tree" / "README.md"
    static = GENERIC_RULES + (
        readme.read_text(encoding="utf-8") if readme.is_file() else ""
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    claude_md = out_dir / "claude_md.md"
    claude_md.write_text(static, encoding="utf-8", newline="\n")
    instruction = str(RECALL_CONFIG["instruction"]).format(
        server=RECALL_CONFIG["server_name"], tool=f"{RECALL_PREFIX}recall_search"
    )
    recall = out_dir / "recall.md"
    recall.write_text(
        instruction.rstrip() + "\n\n" + static, encoding="utf-8", newline="\n"
    )
    return {"claude_md": claude_md, "recall": recall}


def write_mcp_config(path: Path, namespace: str) -> Path:
    env = {
        "RECALL_DSN": os.environ["RECALL_DSN"],
        "RECALL_EMBEDDER": str(RECALL_CONFIG["embedder"]),
        "RECALL_TRUST_MODE": str(RECALL_CONFIG["trust_mode"]),
        "RECALL_TENANT": namespace,
    }
    for passthrough in ("APPDATA", "SystemRoot", "PYTHONPATH", "PATH"):
        value = os.environ.get(passthrough)
        if value:
            env[passthrough] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    str(RECALL_CONFIG["server_name"]): {
                        "command": str(RECALL_CONFIG["command"]),
                        "args": list(RECALL_CONFIG["args"]),
                        "env": env,
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="pilot-001")
    parser.add_argument("--model", default="deepseek/deepseek-v4-flash")
    parser.add_argument("--base-url", default="https://openrouter.ai/api")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--namespace", default="bench-recall-pilot")
    parser.add_argument("--price-in", type=float, default=0.05866)
    parser.add_argument("--price-out", type=float, default=0.11732)
    parser.add_argument("--price-as-of", default="2026-08-22")
    args = parser.parse_args()

    assert_preregistered(REPO)
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set")
    if not os.environ.get("RECALL_DSN"):
        raise SystemExit("RECALL_DSN is not set; the recall arm has no corpus")

    tasks = [task for task in discover_tasks() if task.task_id.startswith("ts-")]
    run_dir = REPO / "results" / args.run_id
    if (run_dir / "records.jsonl").exists():
        raise SystemExit(f"{run_dir} already holds records; refusing to mix runs")
    (run_dir / "streams").mkdir(parents=True, exist_ok=True)

    mcp_config = write_mcp_config(run_dir / "cfg" / "recall.mcp.json", args.namespace)
    signals = with_forbidden_prefixes(
        {
            "bare": AdmissionSignal(arm="bare"),
            "claude_md": AdmissionSignal(arm="claude_md"),
            "recall": AdmissionSignal(arm="recall", mcp_tool_prefixes=(RECALL_PREFIX,)),
        }
    )

    bundles = {
        task.task_id: build_bundles(task, run_dir / "cfg" / task.task_id)
        for task in tasks
    }
    by_id = {task.task_id: task for task in tasks}

    env = {
        "ANTHROPIC_BASE_URL": args.base_url,
        "ANTHROPIC_AUTH_TOKEN": os.environ["OPENROUTER_API_KEY"],
        "ANTHROPIC_API_KEY": "",
    }

    def config_for(task_id: str, seed: int, arm: str, cwd: Path) -> ClaudeExecConfig:
        prompt_file = bundles[task_id].get(arm)
        return ClaudeExecConfig(
            model=args.model,
            cwd=cwd,
            timeout_s=args.timeout,
            env=env,
            bare=True,
            mcp_config=str(mcp_config) if arm == "recall" else None,
            strict_mcp_config=arm == "recall",
            allowed_tools=BASE_TOOLS
            + (
                tuple(f"{RECALL_PREFIX}{t}" for t in RECALL_CONFIG["allowed_tools"])
                if arm == "recall"
                else ()
            ),
            disallowed_tools=DENIED_TOOLS,
            append_system_prompt_file=prompt_file,
            permission_mode="acceptEdits",
            memory_tool_prefix=RECALL_PREFIX,
            stream_dir=run_dir / "streams",
        )

    records_path = run_dir / "records.jsonl"

    async def runner(row, arm):
        task_id, seed = str(row["task_id"]), int(row["seed"])
        workdir = run_dir / "work" / task_id / f"s{seed}" / arm
        digest = sandbox.restore(task_id, workdir)
        record = await run_claude_case(row, arm, config_for(task_id, seed, arm, workdir))
        ok, verdict = run_checker(by_id[task_id], workdir)
        prompt_file = bundles[task_id].get(arm)
        extra = {
            "checker": verdict,
            "sandbox_digest": digest,
            "prompt_sha256": (
                hashlib.sha256(prompt_file.read_bytes()).hexdigest() if prompt_file else None
            ),
        }
        final = replace(
            record,
            success=ok and record.success,
            metadata={**record.metadata, **extra},
        )
        # Fsynced per session: a run that dies keeps every finished cell.
        with records_path.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(final.to_dict()) + "\n")
            sink.flush()
            os.fsync(sink.fileno())
        return final

    rows = [
        {"task_id": task.task_id, "seed": seed, "user_input": task.prompt}
        for task in tasks
        for seed in range(args.seeds)
    ]
    print(
        f"[pilot] {len(rows)} cells x {len(ARMS)} arms = {len(rows) * len(ARMS)} sessions, "
        f"model {args.model}",
        flush=True,
    )
    started = time.monotonic()
    records = await run_grid(rows, ARMS, runner, block_concurrency=1)
    wall_min = (time.monotonic() - started) / 60

    write_jsonl(run_dir / "records.final.jsonl", records)
    report = admit_cells(records, signals, required_arms=ARMS)
    (run_dir / "admission.json").write_text(
        json.dumps(report.summary(), indent=2), encoding="utf-8"
    )
    pricing = {
        args.model: ModelPricing(
            model=args.model,
            usd_per_mtok_input=args.price_in,
            usd_per_mtok_output=args.price_out,
            as_of=args.price_as_of,
            source="https://openrouter.ai/api/v1/models",
        )
    }
    costs = summarize(records, pricing=pricing, model=args.model)
    (run_dir / "costs.json").write_text(json.dumps(costs, indent=2), encoding="utf-8")

    by_arm: dict[str, list] = {arm: [] for arm in ARMS}
    for record in report.admitted:
        by_arm[record.arm].append(record.success)
    print(f"\n[pilot] wall {wall_min:.0f} min, admitted cells {report.admitted_cell_count}, "
          f"discarded {len(report.discarded_cells)} {report.discarded_by_arm()}")
    for arm in ARMS:
        outcomes = by_arm[arm]
        rate = sum(outcomes) / len(outcomes) if outcomes else float("nan")
        print(f"  {arm:<10} success {sum(outcomes)}/{len(outcomes)} = {rate:.3f}")
    searches = [r for r in report.admitted if r.arm == "recall"]
    if searches:
        search_rate = sum(1 for r in searches if r.memory_call_count > 0) / len(searches)
        print(f"  recall search rate: {search_rate:.3f}")
    print(f"  estimated spend: ${costs.get('estimated_usd')} ({costs['total_tokens']} tokens)")
    print(f"  artifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
