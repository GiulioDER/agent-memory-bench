"""Run the four arm oracle and proactive retrieval diagnostic."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.claude_md.adapter import ClaudeMdAdapter
from adapters.oracle_memory.adapter import OracleMemoryAdapter
from adapters.recall.adapter import RecallAdapter
from adapters.recall_prefetch.adapter import RecallPrefetchAdapter
from harness import sandbox
from harness.claude_exec import ClaudeExecConfig, run_claude_case
from harness.gate import AdmissionSignal, admit_cells, with_forbidden_prefixes
from harness.io import write_jsonl
from harness.memory_bundles import MemoryBundleCatalog
from harness.runner import run_grid
from harness.tasks import discover_tasks, run_checker

ARMS = ("claude_md", "recall", "oracle_memory", "recall_prefetch")
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
    target.write_text(generic + (readme.read_text(encoding="utf-8") if readme.is_file() else ""), encoding="utf-8")
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
    parser.add_argument("--dry-run", action="store_true")
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
    catalog = MemoryBundleCatalog.load(oracle_root, corpus, tasks)
    run_dir = REPO / "results" / args.run_id
    if (run_dir / "records.jsonl").exists():
        raise SystemExit(f"{run_dir} already holds records")
    (run_dir / "streams").mkdir(parents=True, exist_ok=True)
    base_prompts = {
        task.task_id: build_static_prompt(task.path, run_dir / "cfg" / task.task_id / "static.md")
        for task in tasks
    }
    claude_adapter = ClaudeMdAdapter(base_prompts[tasks[0].task_id])
    recall_adapter = RecallAdapter(run_dir / "adapter", REPO / "corpus" / "claude_md_bundle_smoke.md")
    oracle_adapter = OracleMemoryAdapter(run_dir / "adapter", base_prompts[tasks[0].task_id], catalog)
    prefetch_adapter = RecallPrefetchAdapter(recall_adapter, run_dir / "adapter", base_prompts[tasks[0].task_id])
    adapters = {
        "claude_md": claude_adapter,
        "recall": recall_adapter,
        "oracle_memory": oracle_adapter,
        "recall_prefetch": prefetch_adapter,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
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
            run_dir / "adapter",
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
                if arm == "claude_md":
                    task_adapter = ClaudeMdAdapter(base_prompts[task.task_id])
                elif arm == "recall":
                    task_adapter = RecallAdapter(run_dir / "adapter", base_prompts[task.task_id])
                elif arm == "oracle_memory":
                    task_adapter = OracleMemoryAdapter(
                        run_dir / "adapter", base_prompts[task.task_id], catalog
                    )
                else:
                    task_adapter = RecallPrefetchAdapter(
                        recall_adapter,
                        run_dir / "adapter",
                        base_prompts[task.task_id],
                        prefetch_runner=(fake_prefetch_runner if args.dry_run else __import__("subprocess").run),
                    )
                spec = task_adapter.build_for_task(
                    run_dir / "cfg" / task.task_id / arm,
                    namespace,
                    task.task_id,
                    task.prompt,
                )
                specs[(task.task_id, arm)] = spec
            except (OSError, RuntimeError, TypeError, ValueError) as error:
                specs[(task.task_id, arm)] = None
                failures[(task.task_id, arm)] = f"{type(error).__name__}: {error}"
    if args.dry_run:
        for task in tasks:
            for arm in run_arms:
                if specs[(task.task_id, arm)] is None:
                    raise SystemExit(f"dry run failed for {task.task_id}/{arm}: {failures[(task.task_id, arm)]}")
        print(f"dry run validated {len(tasks)} tasks and arms {run_arms}; no provider calls made")
        return 0

    signals = with_forbidden_prefixes(
        {
            "claude_md": AdmissionSignal(arm="claude_md"),
            "recall": AdmissionSignal(arm="recall", mcp_tool_prefixes=(RECALL_PREFIX,)),
            "oracle_memory": oracle_adapter.admission_signal(),
            "recall_prefetch": prefetch_adapter.admission_signal(),
        }
    )
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

    rows = [{"task_id": task.task_id, "seed": seed, "user_input": task.prompt} for task in tasks for seed in range(args.seeds)]
    records_path = run_dir / "records.jsonl"

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
        workdir = run_dir / "work" / task_id / f"s{seed}" / arm
        digest = sandbox.restore(task_id, workdir)
        record = await run_claude_case(row, arm, config_for(task_id, arm, workdir))
        ok, verdict = run_checker(by_id[task_id], workdir)
        spec = specs[(task_id, arm)]
        extra = {
            "checker": verdict,
            "sandbox_digest": digest,
            "prompt_sha256": hashlib.sha256(Path(spec.append_system_prompt_file).read_bytes()).hexdigest() if spec.append_system_prompt_file else None,
            **dict(spec.metadata),
        }
        final = replace(record, success=ok and record.success, metadata={**record.metadata, **extra})
        with records_path.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(final.to_dict(), sort_keys=True) + "\n")
            sink.flush()
        return final

    records = await run_grid(rows, run_arms, runner, block_concurrency=1)
    write_jsonl(run_dir / "records.final.jsonl", records)
    report = admit_cells(records, signals, required_arms=run_arms)
    (run_dir / "admission.json").write_text(json.dumps(report.summary(), indent=2), encoding="utf-8")
    (run_dir / "environment.json").write_text(json.dumps({"run_id": args.run_id, "arms": list(run_arms), "model": args.model, "catalog_sha256": catalog.digest}, indent=2), encoding="utf-8")
    print(f"diagnostic complete: {report.admitted_cell_count} admitted cells, {len(report.discarded_cells)} discarded")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
