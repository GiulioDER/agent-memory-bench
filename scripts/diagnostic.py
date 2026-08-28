"""Run the four arm oracle and proactive retrieval diagnostic."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.bare.adapter import BareAdapter
from adapters.claude_md.adapter import ClaudeMdAdapter
from adapters.oracle_memory.adapter import OracleMemoryAdapter
from adapters.recall.adapter import RecallAdapter
from adapters.recall_prefetch.adapter import RecallPrefetchAdapter
from harness import sandbox
from harness.claude_exec import (
    ClaudeExecConfig,
    resolve_claude_executable,
    run_claude_case,
)
from harness.costs import ModelPricing, summarize
from harness.gate import AdmissionSignal, admit_cells, with_forbidden_prefixes
from harness.host_memory import free_memory_mb, wait_for_headroom
from harness.instructions import refuse_shared_prompts_or_exit as refuse_shared_prompts
from harness.io import write_jsonl
from harness.memory_bundles import MemoryBundleCatalog
from harness.memory_startup import probe_mcp_config, run_with_memory_startup_retry
from harness.prereg import assert_preregistered
from harness.runner import run_grid
from harness.tasks import discover_tasks, run_checker
from scripts.pilot import recall_instruction

#: `bare` is FIRST and mandatory. It was dropped after `diagnostic-002` and preregistration 005
#: then declared it mandatory ("without it, 'worse than no memory at all' cannot be
#: expressed"), leaving the runner that supports retries and the diagnostic arms unable to run
#: the suite that needs it. Damage is undefinable without a no-memory reference point.
ARMS = ("bare", "claude_md", "recall", "oracle_memory", "recall_prefetch")
BASE_TOOLS = ("Read", "Grep", "Glob", "Bash", "Write", "Edit")
DENIED_TOOLS = ("Bash(docker:*)", "Bash(docker-compose:*)")
RECALL_CONFIG = json.loads(
    (REPO / "adapters" / "recall" / "config.frozen.json").read_text(encoding="utf-8")
)
RECALL_PREFIX = str(RECALL_CONFIG["tool_prefix"])


def build_static_prompt(task_path: Path, target: Path) -> Path:
    generic = "# Project notes\n\nYou are working in this repository. Keep changes small and leave the tree clean.\n\n"
    readme = task_path / "tree" / "README.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    body = generic + (readme.read_text(encoding="utf-8") if readme.is_file() else "")
    target.write_text(body, encoding="utf-8", newline="\n")
    return target


def synthetic_failure(row: dict, arm: str, error: str, diagnostic: dict | None = None):
    from harness.schema import SessionRecord

    return SessionRecord(
        task_id=str(row["task_id"]),
        arm=arm,
        seed=int(row.get("seed", 0)),
        success=False,
        user_input=str(row.get("user_input", "")),
        error=error,
        metadata={
            "init_present": False,
            "diagnostic_failure": error,
            **({"memory_diagnostic": diagnostic} if diagnostic else {}),
        },
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="diagnostic-001")
    parser.add_argument("--model", default="deepseek/deepseek-v4-flash")
    parser.add_argument("--base-url", default="https://openrouter.ai/api")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--namespace", default="bench-recall-diagnostic")
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve arms, tasks, bundles and prompts, print the grid, and stop. It starts NO "
        "MCP server and runs NO session. Before 2026-08-28 it did both: there was no early "
        "return, so a dry run probed the live memory server and then executed the whole grid, "
        "which only looked like a check because the CI runner has no `claude` binary and every "
        "session failed fast.",
    )
    parser.add_argument(
        "--min-free-mb",
        type=float,
        default=1200.0,
        help=(
            "wait before each cell until the host has this much physical memory free. "
            "A memory arm's MCP server loads its embedder before it can answer, and on "
            "a starved host that start fails silently: the session runs with no tools "
            "and the cell is discarded. Measured at 421 MB free on 2026-08-26, the "
            "recall arm failed nearly every session. 0 disables the wait."
        ),
    )
    parser.add_argument("--headroom-timeout", type=float, default=900.0)
    parser.add_argument(
        "--arm-concurrency",
        type=int,
        default=0,
        help=(
            "how many of a cell's arms run at once. 1 runs them one after another, in a "
            "seeded per-cell random order, which cuts peak memory to about a quarter; four "
            "concurrent sessions took this 12 GB workstation to an out-of-memory reboot. "
            "0, the DEFAULT, is the preregistered shape: all of a cell's arms together, so "
            "no arm systematically runs on a quieter host."
        ),
    )
    parser.add_argument(
        "--recall-instruction",
        choices=("skill", "oneliner"),
        default="skill",
        help=(
            # argparse expands this with `help % params`, so a literal percent sign must be
            # doubled. Undoubled it raised `ValueError: incomplete format` on --help, which no
            # run ever hit because a run never formats the help. The figures are left as they
            # were measured when this text was written.
            "which instruction sits above the static bundle in the recall arm. "
            "pilot-003 and pilot-004 both used `skill`, so that is the default: with "
            "`oneliner` the recall arm is a different treatment from the runs this "
            "diagnostic exists to explain, and its search rate measured 16%% against "
            "pilot-004's 85.7%%."
        ),
    )
    parser.add_argument(
        "--work-root",
        default="",
        help="where session sandboxes are built. Defaults OUTSIDE this repository, because a "
        "sandbox under results/ can reach oracles/, tasks/*/reference/ and corpus/ with one `cd ..`.",
    )
    parser.add_argument("--price-in", type=float, default=0.0826)
    parser.add_argument("--price-out", type=float, default=0.1652)
    parser.add_argument("--price-as-of", default="2026-08-25")
    parser.add_argument(
        "--startup-attempts",
        type=int,
        default=3,
        help=(
            "how many times one session may be run while its treatment fails to wire up. "
            "1 reproduces the pilot-004 behaviour: no retry, and the cell is discarded. "
            "The retry is triggered by the admission surface only, never by the checker."
        ),
    )
    args = parser.parse_args()

    run_arms = tuple(item.strip() for item in args.arms.split(",") if item.strip())
    unknown = [arm for arm in run_arms if arm not in ARMS]
    if unknown:
        raise SystemExit(f"unknown arms {unknown}; choose from {ARMS}")
    tasks = [task for task in discover_tasks() if task.task_id.startswith("ts-")]
    corpus = __import__("harness.adapters.base", fromlist=["CorpusManifest"]).CorpusManifest.load(REPO / "corpus")
    oracle_root = Path(
        os.environ.get("ORACLE_MEMORY_ROOT", str(REPO / "corpus" / "oracle_memory"))
    )

    # The oracle arm needs a bundle per task, and a bundle is built from a task's recorded
    # precursor. The six mid-band tasks added for the abstention suite have no precursor yet, so
    # they have no bundle, and `MemoryBundleCatalog.load` refused the whole catalog: since those
    # tasks landed, `python scripts/diagnostic.py --dry-run` in CI has failed with
    # "references missing bundle". A task the diagnostic cannot serve is EXCLUDED and named, which
    # is a different thing from the catalog being corrupt, and only the second deserves a refusal.
    available = {
        line_bundle["task_id"]
        for line in (oracle_root / "bundles.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
        for line_bundle in [json.loads(line)]
    }
    skipped = [task.task_id for task in tasks if task.task_id not in available]
    if skipped:
        print(
            f"[diagnostic] {len(skipped)} task(s) have no oracle bundle and are excluded from this "
            f"run: {', '.join(skipped)}. Record their precursors and rebuild bundles "
            f"(python -m scripts.build_oracle_bundles) to include them."
        )
        tasks = [task for task in tasks if task.task_id in available]
    if not tasks:
        raise SystemExit("no task has an oracle bundle; nothing this diagnostic can measure")
    catalog = MemoryBundleCatalog.load(oracle_root, corpus, tasks)
    work_root = (
        Path(args.work_root) if args.work_root else sandbox.default_work_root() / args.run_id
    )
    run_dir = REPO / "results" / args.run_id
    if (run_dir / "records.jsonl").exists():
        raise SystemExit(f"{run_dir} already holds records")
    # A dry run must touch NOTHING, including an empty run directory: a stray results/<id>/ is
    # indistinguishable afterwards from a run that started and died, and the next real run with
    # that id then refuses or, worse, appends to it.
    if not args.dry_run:
        (run_dir / "streams").mkdir(parents=True, exist_ok=True)
    cfg_root = (
        Path(tempfile.mkdtemp(prefix="amb-dryrun-")) if args.dry_run else run_dir / "cfg"
    )
    base_prompts = {
        task.task_id: build_static_prompt(task.path, cfg_root / task.task_id / "static.md")
        for task in tasks
    }
    claude_adapter = ClaudeMdAdapter(base_prompts[tasks[0].task_id])
    instruction = recall_instruction(args.recall_instruction)
    recall_adapter = RecallAdapter(
        (cfg_root / "adapter"),
        REPO / "corpus" / "claude_md_bundle_smoke.md",
        instruction=instruction,
    )
    oracle_adapter = OracleMemoryAdapter((cfg_root / "adapter"), base_prompts[tasks[0].task_id], catalog)
    prefetch_adapter = RecallPrefetchAdapter(recall_adapter, (cfg_root / "adapter"), base_prompts[tasks[0].task_id])
    adapters = {
        "claude_md": claude_adapter,
        "recall": recall_adapter,
        "oracle_memory": oracle_adapter,
        "recall_prefetch": prefetch_adapter,
    }
    if not args.dry_run:
        run_dir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        assert_preregistered(REPO)
        if not os.environ.get("OPENROUTER_API_KEY"):
            raise SystemExit("OPENROUTER_API_KEY is not set")
        if not os.environ.get("RECALL_DSN"):
            raise SystemExit("RECALL_DSN is not set")
    else:
        os.environ.setdefault("RECALL_DSN", "postgresql://dry-run.invalid/recall")

    def fake_prefetch_runner(command, **kwargs):
        del command, kwargs
        return __import__("subprocess").CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"bundle": {"items": []}, "abstained": True}), stderr=""
        )

    if args.dry_run:
        prefetch_adapter = RecallPrefetchAdapter(
            recall_adapter,
            (cfg_root / "adapter"),
            base_prompts[tasks[0].task_id],
            prefetch_runner=fake_prefetch_runner,
        )
        adapters["recall_prefetch"] = prefetch_adapter
    if not args.dry_run:
        for arm in run_arms:
            if arm in ("recall", "recall_prefetch"):
                adapters[arm].ingest(corpus, f"{args.namespace}-{arm}")

    specs: dict[tuple[str, str], object | None] = {}
    failures: dict[tuple[str, str], str] = {}
    for task in tasks:
        for arm in run_arms:
            namespace = f"{args.namespace}-{arm}"
            try:
                if arm == "bare":
                    task_adapter = BareAdapter()
                elif arm == "claude_md":
                    task_adapter = ClaudeMdAdapter(base_prompts[task.task_id])
                elif arm == "recall":
                    task_adapter = RecallAdapter(
                        (cfg_root / "adapter"),
                        base_prompts[task.task_id],
                        instruction=instruction,
                    )
                elif arm == "oracle_memory":
                    task_adapter = OracleMemoryAdapter(
                        (cfg_root / "adapter"), base_prompts[task.task_id], catalog
                    )
                else:
                    task_adapter = RecallPrefetchAdapter(
                        recall_adapter,
                        (cfg_root / "adapter"),
                        base_prompts[task.task_id],
                        prefetch_runner=(fake_prefetch_runner if args.dry_run else __import__("subprocess").run),
                    )
                spec = task_adapter.build_for_task(
                    cfg_root / task.task_id / arm,
                    namespace,
                    task.task_id,
                    task.prompt,
                )
                specs[(task.task_id, arm)] = spec
            except (OSError, RuntimeError, TypeError, ValueError) as error:
                specs[(task.task_id, arm)] = None
                failures[(task.task_id, arm)] = f"{type(error).__name__}: {error}"
    prompt_hashes: dict[str, dict[str, str]] = {}
    for arm in run_arms:
        by_task: dict[str, str] = {}
        for task in tasks:
            spec = specs[(task.task_id, arm)]
            if spec is None or not spec.append_system_prompt_file:
                continue
            by_task[task.task_id] = hashlib.sha256(
                Path(spec.append_system_prompt_file).read_bytes()
            ).hexdigest()
        prompt_hashes[arm] = by_task
    refuse_shared_prompts(prompt_hashes)

    startup_probes: dict[str, list[dict]] = {}
    for arm in run_arms if not args.dry_run else ():
        wired = [
            specs[(task.task_id, arm)]
            for task in tasks
            if specs[(task.task_id, arm)] is not None
            and getattr(specs[(task.task_id, arm)], "mcp_config", None)
        ]
        if not wired:
            continue
        probes = await probe_mcp_config(wired[0].mcp_config)
        startup_probes[arm] = [probe.to_dict() for probe in probes]
        if not probes or not all(probe.ok for probe in probes):
            # Refusing here costs nothing. Discovering it 288 sessions later costs the run.
            for probe in probes:
                print(f"preflight {arm}/{probe.server}: ok={probe.ok} {probe.error or ''}")
                if probe.stderr_tail.strip():
                    print(f"  server stderr: {probe.stderr_tail.strip()[-800:]}")
            raise SystemExit(
                f"preflight failed for arm {arm!r}: its MCP server did not answer "
                f"initialize/tools-list, so every one of its sessions would be discarded"
            )
        print(
            f"preflight {arm}: server up in {probes[0].elapsed_ms:.0f} ms, "
            f"tools {list(probes[0].tools)}"
        )

    signals = with_forbidden_prefixes(
        {
            # `bare` is all-negative checks: the forbidden-prefix computation below is what
            # verifies no other arm's tools leaked into it.
            "bare": AdmissionSignal(arm="bare"),
            "claude_md": AdmissionSignal(arm="claude_md"),
            "recall": AdmissionSignal(arm="recall", mcp_tool_prefixes=(RECALL_PREFIX,)),
            "oracle_memory": oracle_adapter.admission_signal(),
            "recall_prefetch": prefetch_adapter.admission_signal(),
        }
    )
    # harness/gate.py has read `prompt_sha256_by_task` all along and nothing ever populated it,
    # so a session that ran with another task's bundle was admitted as evidence.
    signals = {
        arm: (
            replace(
                signal,
                metadata={**signal.metadata, "prompt_sha256_by_task": prompt_hashes[arm]},
            )
            if prompt_hashes.get(arm)
            else signal
        )
        for arm, signal in signals.items()
    }
    if args.dry_run:
        sessions = len(tasks) * args.seeds * len(run_arms)
        print(f"[dry-run] run-id {args.run_id}, model {args.model}, seeds {args.seeds}")
        print(f"[dry-run] arms   {list(run_arms)}")
        print(f"[dry-run] tasks  {len(tasks)}")
        for arm in run_arms:
            distinct = len(set(prompt_hashes.get(arm, {}).values()))
            print(f"[dry-run]   {arm:<16} {distinct} distinct prompt(s) across {len(tasks)} tasks")
        print(f"[dry-run] work root {work_root}")
        print(f"[dry-run] would run {sessions} session(s); no server started, nothing executed")
        return 0

    by_id = {task.task_id: task for task in tasks}
    env = {"ANTHROPIC_BASE_URL": args.base_url, "ANTHROPIC_AUTH_TOKEN": os.environ["OPENROUTER_API_KEY"], "ANTHROPIC_API_KEY": ""}

    def config_for(task_id: str, arm: str, cwd: Path) -> ClaudeExecConfig:
        spec = specs[(task_id, arm)]
        if spec is None:
            raise RuntimeError(failures[(task_id, arm)])
        return ClaudeExecConfig(
            model=args.model,
            cwd=cwd,
            timeout_s=args.timeout,
            env=env,
            bare=spec.bare,
            mcp_config=spec.mcp_config,
            strict_mcp_config=bool(spec.mcp_config),
            allowed_tools=BASE_TOOLS + spec.extra_allowed_tools,
            disallowed_tools=DENIED_TOOLS,
            append_system_prompt_file=spec.append_system_prompt_file,
            permission_mode="acceptEdits",
            memory_tool_prefix=spec.memory_tool_prefix or "mcp__never__",
            stream_dir=run_dir / "streams",
        )

    def claude_code_version() -> str:
        import subprocess

        try:
            result = subprocess.run(
                [resolve_claude_executable("claude"), "--version"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            return result.stdout.strip() or result.stderr.strip()
        except (OSError, subprocess.SubprocessError) as error:
            return f"unavailable: {type(error).__name__}: {error}"

    # Preregistration 003: the environment artifact is written BEFORE the first session, not
    # after it. An artifact written at the end describes a run that already happened, and cannot
    # be the record the run was committed to.
    environment = {
        "run_id": args.run_id,
        "arms": list(run_arms),
        "model": args.model,
        "provider_base_url": args.base_url,
        "claude_code_version": claude_code_version(),
        "timeout_s": args.timeout,
        "permission_mode": "acceptEdits",
        "seeds": args.seeds,
        "repetitions_per_cell": 1,
        "tasks": [task.task_id for task in tasks],
        "namespace": args.namespace,
        "catalog_sha256": catalog.digest,
        "corpus_sessions": len(corpus.sessions),
        "recall_pythonpath": os.environ.get("PYTHONPATH", ""),
        "startup_attempts": args.startup_attempts,
        "startup_preflight": startup_probes,
        "min_free_mb": args.min_free_mb,
        "recall_instruction": args.recall_instruction,
        "recall_instruction_sha256": hashlib.sha256(
            instruction.encode("utf-8")
        ).hexdigest(),
        "arm_concurrency": args.arm_concurrency or None,
        "arm_order_seed": args.run_id,
        "free_mb_at_start": free_memory_mb(),
        "work_root": str(work_root),
        "sandbox_inside_repo": False,
        "pricing": {
            "model": args.model,
            "usd_per_mtok_input": args.price_in,
            "usd_per_mtok_output": args.price_out,
            "as_of": args.price_as_of,
            "source": "https://openrouter.ai/api/v1/models",
        },
    }
    (run_dir / "environment.json").write_text(
        json.dumps(environment, indent=2), encoding="utf-8"
    )

    rows = [{"task_id": task.task_id, "seed": seed, "user_input": task.prompt} for task in tasks for seed in range(args.seeds)]
    records_path = run_dir / "records.jsonl"

    def _workdir(task_id: str, seed: int, arm: str, attempt: int) -> Path:
        # Each attempt gets its own sandbox rather than reusing one: sandbox.restore refuses a
        # directory that already exists, and cleaning it in place would destroy the failed
        # attempt's tree, which is the evidence for what the retry recovered from.
        suffix = "" if attempt == 1 else f".attempt{attempt}"
        return work_root / "work" / task_id / f"s{seed}" / f"{arm}{suffix}"

    async def runner(row, arm):
        task_id, seed = str(row["task_id"]), int(row["seed"])
        if specs[(task_id, arm)] is None:
            failure_diagnostic = None
            if arm == "recall_prefetch":
                failure_diagnostic = {
                    "kind": arm,
                    "prefetch_status": "failed",
                    "query_sha256": None,
                    "result_sha256": None,
                }
            elif arm == "oracle_memory":
                failure_diagnostic = {"kind": arm, "status": "missing"}
            return synthetic_failure(row, arm, failures[(task_id, arm)], failure_diagnostic)
        spec = specs[(task_id, arm)]
        made = {"attempts": 0}
        headroom = None
        if args.min_free_mb > 0:
            headroom = wait_for_headroom(
                args.min_free_mb, timeout_s=args.headroom_timeout
            )
            if not headroom.satisfied:
                print(
                    f"[headroom] {task_id}/{arm}: still {headroom.observed_mb:.0f} MB "
                    f"free after {headroom.waited_s:.0f}s, running anyway and recording it"
                )

        async def one_attempt(attempt_row, attempt_arm, _config):
            made["attempts"] += 1
            workdir = _workdir(task_id, seed, arm, made["attempts"])
            digest = sandbox.restore(task_id, workdir)
            record = await run_claude_case(
                attempt_row, attempt_arm, config_for(task_id, arm, workdir)
            )
            ok, verdict = run_checker(by_id[task_id], workdir)
            extra = {
                "checker": verdict,
                "sandbox_digest": digest,
                "attempt": made["attempts"],
                "host_headroom": headroom.to_dict() if headroom else None,
                "prompt_sha256": hashlib.sha256(Path(spec.append_system_prompt_file).read_bytes()).hexdigest() if spec.append_system_prompt_file else None,
                **dict(spec.metadata),
            }
            final = replace(
                record, success=ok and record.success, metadata={**record.metadata, **extra}
            )
            # Every attempt lands here; records.final.jsonl keeps one record per cell and arm.
            with records_path.open("a", encoding="utf-8") as sink:
                sink.write(json.dumps(final.to_dict(), sort_keys=True) + "\n")
                sink.flush()
            return final

        prefixes = (
            (spec.memory_tool_prefix,) if spec.mcp_config and spec.memory_tool_prefix else ()
        )
        return await run_with_memory_startup_retry(
            row,
            arm,
            config_for(task_id, arm, _workdir(task_id, seed, arm, 1)),
            tool_prefixes=prefixes,
            attempts=args.startup_attempts,
            probe_config=spec.mcp_config,
            probe_min_free_mb=args.min_free_mb,
            runner=one_attempt,
        )

    started = time.monotonic()
    records = await run_grid(
        rows,
        run_arms,
        runner,
        block_concurrency=1,
        arm_concurrency=args.arm_concurrency or None,
        order_seed=args.run_id,
    )
    write_jsonl(run_dir / "records.final.jsonl", records)
    report = admit_cells(records, signals, required_arms=run_arms)
    (run_dir / "admission.json").write_text(json.dumps(report.summary(), indent=2), encoding="utf-8")
    recovered = [
        [record.task_id, record.seed, record.arm]
        for record in records
        if (record.metadata.get("memory_startup") or {}).get("recovered")
    ]
    pricing = {
        args.model: ModelPricing(
            model=args.model,
            usd_per_mtok_input=args.price_in,
            usd_per_mtok_output=args.price_out,
            as_of=args.price_as_of,
            source="https://openrouter.ai/api/v1/models",
        )
    }
    (run_dir / "costs.json").write_text(
        json.dumps(summarize(records, pricing=pricing, model=args.model), indent=2),
        encoding="utf-8",
    )
    # Appended to the artifact written before the first session; nothing above is rewritten.
    # Cells the pilot-004 protocol would have discarded are published here, never folded into
    # the discard count, because a recovered cell changes what that count means.
    environment["recovered_sessions"] = recovered
    environment["wall_minutes"] = round((time.monotonic() - started) / 60, 1)
    (run_dir / "environment.json").write_text(
        json.dumps(environment, indent=2), encoding="utf-8"
    )
    print(
        f"diagnostic complete: {report.admitted_cell_count} admitted cells, "
        f"{len(report.discarded_cells)} discarded, "
        f"{len(recovered)} session(s) recovered by retry"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
