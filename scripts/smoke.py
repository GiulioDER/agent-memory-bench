"""Phase 0 smoke: one task, every wired arm, one seed. Plumbing, not a measurement.

What it proves when it exits 0:

- each adapter ingests the shared corpus through its own write path;
- each arm's session launches, runs against its own sandbox, and produces a parseable stream;
- the admission gate ADMITS every arm (which requires the memory surface to be provably
  present) and discards none;
- the executable checker graded every session, and the artifacts (records, admission,
  costs, streams) are complete.

It deliberately proves nothing about which arm is better: one task at one seed is noise by
construction, and the numbers it prints are for eyeballing the plumbing only.

Usage (credentials come from the environment, see .env.example):

    python -m scripts.smoke --model deepseek/deepseek-v4-flash
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.bare.adapter import BareAdapter
from adapters.claude_md.adapter import ClaudeMdAdapter
from adapters.fs_grep.adapter import FsGrepAdapter
from adapters.recall.adapter import RecallAdapter
from adapters.supermemory.adapter import SupermemoryAdapter
from harness import sandbox
from harness.adapters.base import ArmSpec, CorpusManifest
from harness.adapters.registry import AdapterRegistry
from harness.claude_exec import ClaudeExecConfig, run_claude_case
from harness.costs import add_pricing_arguments, pricing_from_args, summarize
from harness.gate import admit_cells
from harness.io import write_jsonl
from harness.runner import run_grid
from harness.prereg import assert_preregistered

TASK_ID = "smoke-config-port"
FULL_TASK_COUNT = 24
FULL_SEED_COUNT = 3
SMOKE_MAX_SECONDS = 600.0
FULL_RUN_MAX_SECONDS = 18_000.0
PROMPT = (
    "Determine which TCP port this service is configured to listen on, and write it to "
    "RESULT.txt in the repository root: just the number, one line, nothing else."
)
BASE_TOOLS = ("Read", "Grep", "Glob", "Bash", "Write", "Edit")
DENIED_TOOLS = ("Bash(docker:*)", "Bash(docker-compose:*)")


def build_corpus_manifest() -> CorpusManifest:
    """Hash every transcript into corpus/manifest.json and load it back."""

    return CorpusManifest.build(REPO / "corpus")


def check_result(workdir: Path) -> tuple[bool, str]:
    """The executable endpoint: RESULT.txt matches the oracle. A do-nothing session scores 0."""

    expected = (sandbox.oracle(TASK_ID) / "expected.txt").read_text(encoding="utf-8").strip()
    produced = workdir / "RESULT.txt"
    if not produced.is_file():
        return False, "RESULT.txt was never written"
    actual = produced.read_text(encoding="utf-8").strip()
    if actual == expected:
        return True, f"RESULT.txt == {expected!r}"
    return False, f"RESULT.txt held {actual!r}, oracle says {expected!r}"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="deepseek/deepseek-v4-flash")
    parser.add_argument(
        "--arms", default="bare,claude_md,fs_grep,recall,supermemory", help="comma-separated arm roster"
    )
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument(
        "--base-url",
        default="https://openrouter.ai/api",
        help="Anthropic-compatible endpoint the agent talks to. Deliberately NOT read from "
        "the ambient ANTHROPIC_BASE_URL: an inherited value routed one run's OpenRouter key "
        "to api.anthropic.com, and every arm 401ed",
    )
    parser.add_argument("--run-id", default=None)
    # Read from the OpenRouter models endpoint on 2026-08-22 for deepseek/deepseek-v4-flash.
    # Override for any other model; the costs artifact records what was used.
    add_pricing_arguments(parser)
    args = parser.parse_args()

    assert_preregistered(REPO)
    smoke_started = time.monotonic()

    arms = tuple(arm.strip() for arm in args.arms.split(",") if arm.strip())
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set; the agent cannot run")
    if "supermemory" in arms:
        missing = []
        if not os.environ.get("SUPERMEMORY_PLUGIN_DIR"):
            missing.append("SUPERMEMORY_PLUGIN_DIR")
        if not (
            os.environ.get("SUPERMEMORY_CC_API_KEY")
            or os.environ.get("SUPERMEMORY_API_KEY")
        ):
            missing.append("SUPERMEMORY_CC_API_KEY or SUPERMEMORY_API_KEY")
        if missing:
            raise SystemExit("Supermemory is not configured; set " + ", ".join(missing))

    run_id = args.run_id or f"smoke-{time.strftime('%Y%m%d-%H%M%S')}"
    run_dir = REPO / "results" / run_id
    if run_dir.exists():
        raise SystemExit(f"run dir {run_dir} already exists; refusing to mix runs")
    (run_dir / "streams").mkdir(parents=True)

    corpus = build_corpus_manifest()
    base_prompt = REPO / "corpus" / "claude_md_bundle_smoke.md"
    staging = run_dir / "staging"

    registry = AdapterRegistry()
    registry.register(BareAdapter())
    registry.register(ClaudeMdAdapter(base_prompt))
    registry.register(FsGrepAdapter(staging, base_prompt))
    registry.register(RecallAdapter(staging, base_prompt))
    registry.register(SupermemoryAdapter(staging, base_prompt))

    # Ingest: each memory arm through its own write path, metered where measurable.
    ingest_started = time.monotonic()
    ingest_reports = []
    for arm in arms:
        adapter = registry.get(arm)
        namespace = f"smoke-{arm}-0"
        print(f"[ingest] {arm} -> {namespace}", flush=True)
        ingest_reports.append(adapter.ingest(corpus, namespace))
    ingest_elapsed_s = time.monotonic() - ingest_started

    signals = registry.signals(arms)

    # One sandbox per (task, arm), restored from the same fixture.
    specs: dict[str, ArmSpec] = {}
    workdirs: dict[str, Path] = {}
    digests: dict[str, str] = {}
    for arm in arms:
        workdir = run_dir / "work" / TASK_ID / arm
        digests[arm] = sandbox.restore(TASK_ID, workdir)
        workdirs[arm] = workdir
        spec = registry.get(arm).build(run_dir / "cfg" / arm, f"smoke-{arm}-0")
        specs[arm] = spec
        overlay = spec.metadata.get("sandbox_overlay")
        if overlay:
            shutil.copytree(overlay, workdir / "memory")

    env = {
        "ANTHROPIC_BASE_URL": args.base_url,
        "ANTHROPIC_AUTH_TOKEN": os.environ["OPENROUTER_API_KEY"],
        "ANTHROPIC_API_KEY": "",
    }

    def config_for(arm: str) -> ClaudeExecConfig:
        spec = specs[arm]
        return ClaudeExecConfig(
            model=args.model,
            cwd=workdirs[arm],
            timeout_s=args.timeout,
            env={**env, **spec.env},
            bare=spec.bare,
            config_dir=spec.config_dir,
            mcp_config=spec.mcp_config,
            strict_mcp_config=bool(spec.mcp_config),
            allowed_tools=BASE_TOOLS + spec.extra_allowed_tools,
            disallowed_tools=DENIED_TOOLS,
            append_system_prompt_file=spec.append_system_prompt_file,
            permission_mode="acceptEdits",
            memory_tool_prefix=spec.memory_tool_prefix or "mcp__",
            stream_dir=run_dir / "streams",
        )

    async def runner(row, arm):
        record = await run_claude_case(row, arm, config_for(arm))
        spec = specs[arm]
        success, verdict = check_result(workdirs[arm])
        extra = {
            "checker": verdict,
            "sandbox_digest": digests[arm],
            "sandbox_paths_present": ["memory"] if (workdirs[arm] / "memory").is_dir() else [],
        }
        for key in ("prompt_sha256",):
            if key in spec.metadata:
                extra[key] = spec.metadata[key]
        return replace(
            record,
            success=success and record.success,
            config_dir_digest=spec.config_dir_digest,
            hook_ledger=(
                registry.get("supermemory").read_hook_ledger(
                    record.metadata.get("session_id"), spec.config_dir
                )
                if arm == "supermemory" and spec.config_dir is not None
                else record.hook_ledger
            ),
            metadata={**record.metadata, **extra},
        )

    rows = [{"task_id": TASK_ID, "seed": 0, "user_input": PROMPT}]
    print(f"[run] {len(rows)} cell(s) x {len(arms)} arm(s), model {args.model}", flush=True)
    sessions_started = time.monotonic()
    records = await run_grid(rows, arms, runner, block_concurrency=1)
    session_elapsed_s = time.monotonic() - sessions_started
    total_elapsed_s = time.monotonic() - smoke_started
    setup_elapsed_s = max(0.0, total_elapsed_s - ingest_elapsed_s - session_elapsed_s)
    projected_full_run_s = (
        setup_elapsed_s
        + ingest_elapsed_s
        + session_elapsed_s * FULL_TASK_COUNT * FULL_SEED_COUNT
    )
    timing_ok = (
        total_elapsed_s <= SMOKE_MAX_SECONDS
        and projected_full_run_s <= FULL_RUN_MAX_SECONDS
    )

    write_jsonl(run_dir / "records.jsonl", records)
    report = admit_cells(records, signals, required_arms=arms)
    (run_dir / "admission.json").write_text(
        json.dumps(report.summary(), indent=2), encoding="utf-8"
    )
    pricing = pricing_from_args(
        args, model=args.model, source="https://openrouter.ai/api/v1/models"
    )
    costs = summarize(records, ingest_reports, pricing=pricing, model=args.model)
    (run_dir / "costs.json").write_text(json.dumps(costs, indent=2), encoding="utf-8")
    (run_dir / "environment.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "model": args.model,
                "arms": {arm: registry.get(arm).describe() for arm in arms},
                "ingest": [r.to_dict() for r in ingest_reports],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "timing.json").write_text(
        json.dumps(
            {
                "smoke_elapsed_s": total_elapsed_s,
                "setup_elapsed_s": setup_elapsed_s,
                "ingest_elapsed_s": ingest_elapsed_s,
                "agent_session_elapsed_s": session_elapsed_s,
                "full_run_tasks": FULL_TASK_COUNT,
                "full_run_seeds": FULL_SEED_COUNT,
                "projected_full_run_s": projected_full_run_s,
                "smoke_max_s": SMOKE_MAX_SECONDS,
                "full_run_max_s": FULL_RUN_MAX_SECONDS,
                "timing_gate_passed": timing_ok,
                "projection_formula": "ingest_once + smoke_agent_session_time * 24 * 3",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    for record in records:
        meta = record.metadata
        print(
            f"  {record.arm:<10} success={record.success} "
            f"memory_calls={record.memory_call_count} "
            f"tokens={record.input_tokens}/{record.output_tokens} "
            f"wall={None if record.wall_time_ms is None else round(record.wall_time_ms / 1000, 1)}s "
            f"checker={meta.get('checker')!r} error={record.error!r}"
        )
    print(
        f"\n  admitted cells: {report.admitted_cell_count}, "
        f"discarded: {len(report.discarded_cells)} {dict(report.discarded_by_arm())}"
    )
    print(f"  estimated spend: ${costs.get('estimated_usd')} ({costs['total_tokens']} tokens)")
    print(
        f"  timing: smoke={total_elapsed_s:.1f}s, projected full={projected_full_run_s / 60:.1f}m, "
        f"gate={'PASS' if timing_ok else 'FAIL'}"
    )
    print(f"  artifacts: {run_dir}")

    if report.discarded_cells or not timing_ok:
        for verdict in report.verdicts:
            if not verdict.admitted:
                print(f"  DISCARD {verdict.arm}: {verdict.reasons}")
        if not timing_ok:
            print(
                f"  TIMING GATE FAILED: smoke must be <= {SMOKE_MAX_SECONDS:.0f}s and "
                f"projected full run must be <= {FULL_RUN_MAX_SECONDS / 3600:.1f}h"
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
