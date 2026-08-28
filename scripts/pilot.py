"""Phase 2 pilot: the paired grid over the full task set. A MEASUREMENT.

Refuses to start while `preregistration/` is dirty; the committed record for the first run is
`preregistration/000-pilot.md`. Everything the pilot exists to produce is written there:
task screening (ceiling and floor), variance for the power analysis, and the mechanism
metrics (search rate, governing-session-reached rate) beside the outcome.

Per-task system prompts: the `claude_md` arm receives the fixture's own README as its static
bundle; every memory arm receives the identical bundle with a memory instruction at the TOP
(the buried-instruction lesson); `bare` receives nothing. The governing facts are verifiably
absent from bundles and fixtures (`scripts/audit_corpus.py` locus check), so the only route to
them is memory.

    python -m scripts.pilot --run-id pilot-001

Environment: OPENROUTER_API_KEY; RECALL_DSN pointing at the bench database whose tenant holds
the ingested corpus; PYTHONPATH pinned to the recall checkout that serves the MCP server (the
shared editable install resolves `recall` from an arbitrary worktree otherwise, which is a
measured hazard).

## Three things this runner changed on 2026-08-28, and why each one moved

1. **Every arm is built by its adapter.** This script used to construct bundles, MCP configs and
   admission signals inline, with a hardcoded four-arm tuple, so `adapters/` was reviewable code
   that the measured path did not execute and `fs_grep` could not be run at all. A competitor
   integrating through `harness/adapters/base.py` would have been running a different code path
   from the one that produced recall's numbers.
2. **Every memory arm gets the same instruction.** See `harness/instructions.py`. Pass
   `--memory-instruction protocol` for the fair variant; `skill` and `oneliner` remain, because
   `pilot-002` through `pilot-004` ran `skill` and a rerun is only comparable against that text.
3. **Sandboxes are built OUTSIDE this repository.** They used to live at
   `results/<run>/work/...`, six directories below `oracles/`, with the agent holding unrestricted
   `Bash` and its own absolute path. Nothing was ever read; nothing stopped it either.
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

from adapters.bare.adapter import BareAdapter
from adapters.claude_md.adapter import ClaudeMdAdapter
from adapters.fs_grep.adapter import FS_GREP_SEARCH_SENTENCE, FsGrepAdapter
from adapters.recall.adapter import RecallAdapter
from harness import instructions, sandbox
from harness.abstention import declines
from harness.adapters.base import ArmSpec, CorpusManifest, IngestReport, MemoryAdapter
from harness.adapters.registry import AdapterRegistry
from harness.claude_exec import ClaudeExecConfig, run_claude_case
from harness.costs import ModelPricing, efficiency, summarize
from harness.damage import CONDITIONS, outcome_for
from harness.gate import admit_cells, with_forbidden_prefixes
from harness.instructions import refuse_shared_prompts_or_exit as refuse_shared_prompts
from harness.io import write_jsonl
from harness.placebo import length_metadata, render_placebo
from harness.prereg import assert_preregistered
from harness.runner import run_grid
from harness.tasks import discover_tasks, run_checker

#: Every arm this runner knows how to build. `protocol` and `fs_grep` joined on 2026-08-28.
ARMS = ("bare", "placebo", "claude_md", "protocol", "fs_grep", "recall")
DEFAULT_ARMS = ("bare", "claude_md", "recall")

#: Arms whose treatment is a memory surface, and which therefore share the memory protocol.
MEMORY_ARMS = frozenset({"fs_grep", "recall"})

#: Arms that are a static system-prompt file and nothing else.
STATIC_ARMS = frozenset({"placebo", "claude_md", "protocol"})

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

#: The recall arm's one line in the shared protocol's slot.
RECALL_SEARCH_SENTENCE = (
    "This project keeps a searchable memory of past work sessions; search it with the "
    f"`{RECALL_PREFIX}recall_search` tool before acting."
)

#: The instruction-only control arm's slot. It has no memory layer, so it is pointed at the only
#: thing it does have. This is what isolates the coaching from the retrieval: if `protocol` moves
#: against `claude_md`, part of any memory arm's lift is the instruction rather than the store.
PROTOCOL_SEARCH_SENTENCE = (
    "This project has no memory store beyond the repository in front of you; search the "
    "repository itself with `Grep` and `Read` before acting."
)


def recall_instruction(variant: str, *, neutral: bool = False) -> str:
    """The recall arm's memory instruction.

    ``oneliner`` is the frozen sentence from `config.frozen.json`. ``skill`` is the
    check-memory-before-acting skill, copied VERBATIM from recall's plugin (provenance: recall
    origin/master 438779ff, sha256 prefix 0ea85e7aab4736d5, copied 2026-08-24); `pilot-002`
    through `pilot-004` ran it and it is kept unchanged so a rerun stays comparable to them.

    ⚠️ ``skill`` is NOT fair across arms and should not be used for a competitor comparison. It is
    5,428 characters against `fs_grep`'s 231 and `claude_md`'s zero, and most of it is generic
    coaching rather than anything about recall. ``protocol`` is the fair variant: the shared
    `adapters/_shared/memory_protocol.md` plus recall's own capped result-schema appendix.
    """

    if variant == "oneliner":
        return str(RECALL_CONFIG["instruction"]).format(
            server=RECALL_CONFIG["server_name"], tool=f"{RECALL_PREFIX}recall_search"
        )
    if variant == "skill":
        text = (REPO / "adapters" / "recall" / "skill.md").read_text(encoding="utf-8")
        # Strip the plugin frontmatter block; the body is the instruction.
        if text.startswith("---"):
            text = text.split("---", 2)[2]
        return text.strip()
    if variant == "protocol":
        return instructions.compose("recall", RECALL_SEARCH_SENTENCE, neutral=neutral)
    raise ValueError(f"unknown recall instruction variant {variant!r}")


def memory_instructions(variant: str, arms: tuple[str, ...], *, neutral: bool = False) -> dict[str, str]:
    """The instruction each arm carries, keyed by arm. Arms with no memory surface carry "".

    Under ``protocol`` every memory arm gets `adapters/_shared/memory_protocol.md` verbatim plus its
    own capped appendix, and the fairness assertion below is meaningful. Under ``skill`` or
    ``oneliner`` the arms are deliberately NOT matched, because those variants exist to reproduce
    runs that were not matched, and the assertion is skipped with that stated in the artifact.
    """

    texts = {arm: "" for arm in arms}
    if "recall" in texts:
        texts["recall"] = recall_instruction(variant, neutral=neutral)
    if "fs_grep" in texts:
        texts["fs_grep"] = (
            FsGrepAdapter.shared_instruction(neutral=neutral)
            if variant == "protocol"
            # The historical sentence, so a `skill`/`oneliner` rerun reproduces the old asymmetry
            # rather than half-fixing it and being comparable to neither.
            else instructions.compose("fs_grep", FS_GREP_SEARCH_SENTENCE, neutral=neutral)
        )
    if "protocol" in texts:
        texts["protocol"] = instructions.compose(
            "protocol", PROTOCOL_SEARCH_SENTENCE, neutral=neutral
        )
    if variant == "protocol":
        instructions.assert_shared_protocol(texts, neutral=neutral)
    return texts


def build_bundles(task, out_dir: Path, texts: dict[str, str]) -> dict[str, Path]:
    """Per-task system prompt files, one per arm that takes one.

    Every arm's bundle is the SAME static half (generic rules plus the fixture README); the only
    difference is the instruction above it, and `placebo`, which replaces the static half with
    length-matched neutral prose and carries no instruction at all.
    """

    readme = task.path / "tree" / "README.md"
    static = GENERIC_RULES + (
        readme.read_text(encoding="utf-8") if readme.is_file() else ""
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    bundles: dict[str, Path] = {}

    claude_md = out_dir / "claude_md.md"
    claude_md.write_text(static, encoding="utf-8", newline="\n")
    bundles["claude_md"] = claude_md

    placebo = out_dir / "placebo.md"
    placebo.write_text(render_placebo(static), encoding="utf-8", newline="\n")
    bundles["placebo"] = placebo

    for arm in ("protocol", "fs_grep", "recall"):
        text = texts.get(arm, "")
        if not text:
            continue
        path = out_dir / f"{arm}.md"
        path.write_text(text.rstrip() + "\n\n" + static, encoding="utf-8", newline="\n")
        bundles[arm] = path
    return bundles


def adapter_for(
    arm: str, task_bundle: dict[str, Path], staging: Path, texts: dict[str, str]
) -> MemoryAdapter:
    """The adapter instance that builds ONE arm for ONE task.

    Per task, not per run. One adapter holding one prompt across a 24-task grid is exactly the
    defect `diagnostic-001` shipped: every recall session received `ts-append-only`'s README while
    every other arm received its own, which turned that arm's static half into misdirection about a
    different repository and voided three of five preregistered contrasts.

    The static half handed to every arm is the SAME file (`task_bundle["claude_md"]`), which is what
    makes the additive design true by construction rather than by review.
    """

    static = task_bundle["claude_md"]
    if arm == "bare":
        return BareAdapter()
    if arm == "claude_md":
        return ClaudeMdAdapter(static)
    if arm in ("placebo", "protocol"):
        # Same mechanism as claude_md: one static file, no memory surface. `placebo` replaces the
        # static half with length-matched neutral prose; `protocol` keeps it and adds the shared
        # memory protocol, which is what isolates the instruction from the retrieval.
        return ClaudeMdAdapter(task_bundle[arm], name=arm)
    # `or None` rather than `[arm]`: an arm absent from this run has no entry, and an arm whose
    # entry is the empty string wants its adapter's own default rather than a two-newline
    # "instruction". Indexing here raised KeyError for any arm outside the run, on a path no dry
    # run reaches because a dry run returns before the registry is built.
    if arm == "fs_grep":
        return FsGrepAdapter(staging, static, instruction=texts.get("fs_grep") or None)
    if arm == "recall":
        return RecallAdapter(staging, static, instruction=texts.get("recall") or None)
    raise ValueError(f"no adapter for arm {arm!r}")


def build_registry(
    staging: Path, any_bundle: dict[str, Path], texts: dict[str, str], arms: tuple[str, ...]
) -> AdapterRegistry:
    """A registry holding one instance per arm IN THIS RUN, for admission signals and `describe()`.

    The per-session ArmSpec comes from :func:`adapter_for`, which is per task. This registry exists
    for the cross-arm computations that need the whole roster: forbidden tool prefixes are computed
    over the arms actually wired in, because an arm cannot be contaminated by a product that never
    ran.
    """

    registry = AdapterRegistry()
    for arm in sorted(arms):
        if arm in ("placebo", "protocol") and arm not in any_bundle:
            continue
        registry.register(adapter_for(arm, any_bundle, staging, texts))
    return registry


def classify_cell(
    task, workdir: Path, condition: str, checker_ok: bool, verdict: str, response: str
) -> dict[str, object]:
    """The three-way outcome for one finished cell, or {} when no condition is being measured.

    Separate from `runner` so it can be tested against a real sandbox without running a session.
    It must be CALLED from inside the runner: the damage detector reads the finished working tree,
    and after the grid returns that tree is gone, so a later pass could not recover the outcome
    at any price short of re-running the grid.
    """

    if not condition:
        return {}
    outcome, reason = outcome_for(
        task.path, workdir, task.oracle_dir, condition, checker_ok, verdict
    )
    abstained, marker = declines(response)
    return {
        "condition": condition,
        "outcome": outcome.value,
        "damage_reason": reason,
        "abstained": abstained,
        "abstain_marker": marker,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="pilot-001")
    parser.add_argument("--model", default="deepseek/deepseek-v4-flash")
    parser.add_argument("--base-url", default="https://openrouter.ai/api")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--namespace", default="bench-recall-pilot")
    parser.add_argument(
        "--memory-instruction",
        "--recall-instruction",
        dest="memory_instruction",
        choices=("oneliner", "skill", "protocol"),
        default="oneliner",
        help="which instruction the memory arms carry; recorded in the artifacts. `protocol` is "
        "the only variant in which the arms are matched: it gives every memory arm the shared "
        "adapters/_shared/memory_protocol.md plus that product's own capped appendix. `skill` "
        "reproduces pilot-002 through pilot-004, in which the recall arm carried 5,428 characters "
        "and no other arm carried more than 231.",
    )
    parser.add_argument(
        "--neutral-protocol",
        action="store_true",
        help="strip the two protocol sentences that pre-answer an abstention condition ('the code "
        "wins when they disagree', 'do not conclude the project has no opinion'). Required for "
        "any run of the preregistration-005 abstention suite, where those sentences hand every arm "
        "the answer to what is being measured. Not comparable with a run without it.",
    )
    parser.add_argument(
        "--arms",
        default=",".join(DEFAULT_ARMS),
        help=f"comma-separated subset of {','.join(ARMS)}",
    )
    parser.add_argument(
        "--tasks",
        default="",
        help="comma-separated task ids to run; default is every ts-* task. A subset is for "
        "calibrating new tasks, never for a preregistered comparison, whose task set is "
        "fixed by its record.",
    )
    parser.add_argument(
        "--corpus-root",
        default="",
        help="the corpus feed to ingest. Defaults to corpus/. Point it at a directory built by "
        "scripts/assemble_condition_corpus.py to run one of preregistration 005's conditions, "
        "whose feed differs from the base corpus by design.",
    )
    parser.add_argument(
        "--condition",
        default="",
        choices=("", *CONDITIONS),
        help="the corpus condition this run is measuring. When set, every finished cell is "
        "classified through its task's damage detector while the sandbox still exists, and the "
        "outcome is written to the record. Without it a cell records pass or fail only, which is "
        "what every run before the abstention suite needed.",
    )
    parser.add_argument(
        "--work-root",
        default="",
        help="where session sandboxes are built. Defaults to a directory OUTSIDE this repository "
        "(harness.sandbox.default_work_root), because a sandbox under results/ can reach "
        "oracles/, tasks/*/reference/ and corpus/ with one `cd ..`.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve arms, tasks and seeds, print the grid, and stop before writing or "
        "executing anything. This is how you check a command line; running it with a "
        "placeholder API key instead executes the whole grid and burns the run id.",
    )
    parser.add_argument("--price-in", type=float, default=0.05866)
    parser.add_argument("--price-out", type=float, default=0.11732)
    parser.add_argument("--price-as-of", default="2026-08-22")
    args = parser.parse_args()

    # Before the dry-run return, deliberately: a dry run is how you check a command line, so it has
    # to catch the two things that make a real run worthless. A recall arm with no DSN is a run
    # whose treatment is silently absent, which is exactly what the admission gate exists to catch
    # 216 sessions later.
    assert_preregistered(REPO)
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set")

    run_arms = tuple(arm.strip() for arm in args.arms.split(",") if arm.strip())
    unknown = [arm for arm in run_arms if arm not in ARMS]
    if unknown:
        raise SystemExit(f"unknown arms {unknown}; choose from {ARMS}")
    if "protocol" in run_arms and args.memory_instruction != "protocol":
        raise SystemExit(
            "the `protocol` arm is the instruction-only control for the shared memory protocol, "
            "so it is only meaningful with --memory-instruction protocol. With `skill` or "
            "`oneliner` it would carry a different instruction from the memory arms it exists to "
            "be compared against."
        )
    # Only the recall arm reads a corpus through a database. Demanding a DSN for a run that has no
    # recall arm would make a bare-only calibration impossible without standing up a database it
    # never queries.
    #
    # And not for a dry run either, whatever the arms. A dry run resolves the grid and stops before
    # any session or query, so requiring a database there defeats the point of having a cheap
    # check: it made `--dry-run --arms bare,recall` impossible anywhere the database was not
    # already up, which is exactly where you most want to check a command line first.
    if "recall" in run_arms and not args.dry_run and not os.environ.get("RECALL_DSN"):
        raise SystemExit("RECALL_DSN is not set; the recall arm has no corpus")

    tasks = [task for task in discover_tasks() if task.task_id.startswith("ts-")]
    if args.tasks:
        wanted = [item.strip() for item in args.tasks.split(",") if item.strip()]
        available = {task.task_id for task in tasks}
        missing = [task_id for task_id in wanted if task_id not in available]
        if missing:
            raise SystemExit(f"unknown task(s) {missing}; a silent subset is a different run")
        tasks = [task for task in tasks if task.task_id in set(wanted)]
    if not tasks:
        raise SystemExit("no tasks selected")

    texts = memory_instructions(
        args.memory_instruction, run_arms, neutral=args.neutral_protocol
    )

    if args.dry_run:
        # Placed BEFORE the run directory is created, so a dry run touches nothing at all.
        sessions = len(tasks) * args.seeds * len(run_arms)
        manifest = instructions.instruction_manifest(texts)
        print(f"[dry-run] run-id {args.run_id}, model {args.model}, seeds {args.seeds}")
        print(f"[dry-run] arms   {list(run_arms)}")
        print(f"[dry-run] instruction variant {args.memory_instruction!r}, "
              f"neutral={args.neutral_protocol}")
        for arm in run_arms:
            print(f"[dry-run]   {arm:<10} instruction {manifest[arm]['bytes']:>5} bytes")
        print(f"[dry-run] tasks  {len(tasks)}: {', '.join(task.task_id for task in tasks)}")
        print(f"[dry-run] work root {args.work_root or sandbox.default_work_root()}")
        print(f"[dry-run] would run {sessions} session(s); nothing written, nothing executed")
        return 0

    run_dir = REPO / "results" / args.run_id
    if (run_dir / "records.jsonl").exists():
        raise SystemExit(f"{run_dir} already holds records; refusing to mix runs")
    (run_dir / "streams").mkdir(parents=True, exist_ok=True)
    work_root = Path(args.work_root) if args.work_root else sandbox.default_work_root() / args.run_id
    staging = work_root / "staging"

    bundles = {
        task.task_id: build_bundles(task, run_dir / "cfg" / task.task_id, texts)
        for task in tasks
    }
    registry = build_registry(staging, bundles[tasks[0].task_id], texts, run_arms)

    # Ingestion, for the arms whose store this runner owns. recall's tenant is indexed out of band
    # against the frozen corpus manifest; fs_grep's render is local, cheap and reproducible here.
    ingest_reports: list[IngestReport] = []
    corpus_root = Path(args.corpus_root) if args.corpus_root else REPO / "corpus"
    if not (corpus_root / "manifest.json").is_file():
        raise SystemExit(
            f"{corpus_root} holds no manifest.json. A condition corpus is built by "
            f"scripts/assemble_condition_corpus.py, which writes one; running against a feed "
            f"whose bytes nothing has hashed is how two arms end up ingesting different corpora."
        )
    if "fs_grep" in run_arms:
        corpus = CorpusManifest.load(corpus_root)
        print(f"[ingest] fs_grep from {corpus_root}", flush=True)
        ingest_reports.append(registry.get("fs_grep").ingest(corpus, args.namespace))

    # One ArmSpec per (task, arm), built by that arm's own adapter. This is the measured path, and
    # until 2026-08-28 it was inline code here instead, so `adapters/` was reviewable and not run.
    specs: dict[tuple[str, str], ArmSpec] = {}
    for task in tasks:
        for arm in run_arms:
            adapter = adapter_for(arm, bundles[task.task_id], staging, texts)
            specs[(task.task_id, arm)] = adapter.build_for_task(
                run_dir / "cfg" / task.task_id / arm,
                args.namespace,
                task.task_id,
                task.prompt,
            )

    prompt_hashes: dict[str, dict[str, str]] = {}
    for arm in run_arms:
        by_task: dict[str, str] = {}
        for task in tasks:
            prompt = specs[(task.task_id, arm)].append_system_prompt_file
            if prompt is not None:
                by_task[task.task_id] = hashlib.sha256(Path(prompt).read_bytes()).hexdigest()
        prompt_hashes[arm] = by_task
    refuse_shared_prompts(prompt_hashes)

    signals = with_forbidden_prefixes(
        {
            arm: replace(
                registry.get(arm).admission_signal(),
                metadata={
                    **registry.get(arm).admission_signal().metadata,
                    **(
                        {"prompt_sha256_by_task": prompt_hashes[arm]}
                        if prompt_hashes.get(arm)
                        else {}
                    ),
                },
            )
            for arm in run_arms
        }
    )

    (run_dir / "environment.json").write_text(
        json.dumps(
            {
                "run_id": args.run_id,
                "model": args.model,
                "arms": list(run_arms),
                "memory_instruction": args.memory_instruction,
                "neutral_protocol": args.neutral_protocol,
                # The fairness disclosure, published beside the success rates. Under `skill` the
                # recall arm carries thousands of bytes more than any other; under `protocol` the
                # gap is each product's capped result-schema appendix and nothing else.
                "instruction_manifest": instructions.instruction_manifest(texts),
                "instruction_excess_bytes": instructions.excess_over_protocol(
                    texts, neutral=args.neutral_protocol
                ),
                "instruction_arms_matched": args.memory_instruction == "protocol",
                "placebo_length_metric": "whitespace_tokens_and_lines",
                "placebo_length_match": {
                    task_id: length_metadata(
                        (bundle["claude_md"]).read_text(encoding="utf-8"),
                        (bundle["placebo"]).read_text(encoding="utf-8"),
                    )
                    for task_id, bundle in bundles.items()
                    if "placebo" in bundle
                },
                "prompt_sha256_by_task": prompt_hashes,
                "namespace": args.namespace,
                "work_root": str(work_root),
                "sandbox_inside_repo": False,
                "adapters": {
                    arm: registry.get(arm).describe()
                    for arm in run_arms
                    if arm in registry.names()
                },
                "ingest": [report.to_dict() for report in ingest_reports],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    by_id = {task.task_id: task for task in tasks}

    env = {
        "ANTHROPIC_BASE_URL": args.base_url,
        "ANTHROPIC_AUTH_TOKEN": os.environ["OPENROUTER_API_KEY"],
        "ANTHROPIC_API_KEY": "",
    }

    def config_for(task_id: str, seed: int, arm: str, cwd: Path) -> ClaudeExecConfig:
        """Everything the harness controls is here; everything the product controls is in the spec.

        The split is the neutrality claim made mechanical: model, timeout, tool allow/deny list,
        permission mode and sandbox are identical for every arm and set here, and the only per-arm
        values are the four the adapter returned.
        """

        spec = specs[(task_id, arm)]
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

    records_path = run_dir / "records.jsonl"
    fs_grep_memory = staging / args.namespace / "memory" if "fs_grep" in run_arms else None

    async def runner(row, arm):
        task_id, seed = str(row["task_id"]), int(row["seed"])
        workdir = work_root / "work" / task_id / f"s{seed}" / arm
        overlay = fs_grep_memory if arm == "fs_grep" else None
        digest = sandbox.restore(task_id, workdir, overlay=overlay)
        record = await run_claude_case(row, arm, config_for(task_id, seed, arm, workdir))
        ok, verdict = run_checker(by_id[task_id], workdir)
        prompt_file = specs[(task_id, arm)].append_system_prompt_file

        # Classify HERE, not in the analysis. A damage detector needs the finished working tree,
        # and by the time anything reads records.jsonl the sandbox is gone. Without this the
        # outcome could only be re-derived by re-running the grid.
        condition_extra = classify_cell(
            by_id[task_id], workdir, args.condition, ok, verdict, record.response or ""
        )

        extra = {
            "checker": verdict,
            **condition_extra,
            # Compared ACROSS a cell's arms by harness.gate.admit_cells. Recorded since the first
            # commit and, until 2026-08-28, read by nothing.
            "sandbox_digest": digest,
            "sandbox_paths_present": (
                [p for p in ("memory",) if (workdir / p).is_dir()]
            ),
            "prompt_sha256": (
                hashlib.sha256(Path(prompt_file).read_bytes()).hexdigest()
                if prompt_file
                else None
            ),
            "instruction_bytes": len(texts.get(arm, "").encode("utf-8")),
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
        f"[pilot] {len(rows)} cells x {len(run_arms)} arms = {len(rows) * len(run_arms)} sessions, "
        f"model {args.model}",
        flush=True,
    )
    started = time.monotonic()
    records = await run_grid(rows, run_arms, runner, block_concurrency=1)
    wall_min = (time.monotonic() - started) / 60

    write_jsonl(run_dir / "records.final.jsonl", records)
    report = admit_cells(records, signals, required_arms=run_arms)
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
    costs = summarize(records, ingest_reports, pricing=pricing, model=args.model)
    admitted_cells = {record.cell: True for record in report.admitted}
    costs["efficiency"] = efficiency(records, admitted_cells=admitted_cells)
    (run_dir / "costs.json").write_text(json.dumps(costs, indent=2), encoding="utf-8")

    by_arm: dict[str, list] = {arm: [] for arm in run_arms}
    for record in report.admitted:
        by_arm[record.arm].append(record.success)
    print(f"\n[pilot] wall {wall_min:.0f} min, admitted cells {report.admitted_cell_count}, "
          f"discarded {len(report.discarded_cells)} {report.discarded_by_arm()}")
    for arm in run_arms:
        outcomes = by_arm[arm]
        rate = sum(outcomes) / len(outcomes) if outcomes else float("nan")
        eff = costs["efficiency"].get(arm, {})
        print(
            f"  {arm:<10} success {sum(outcomes)}/{len(outcomes)} = {rate:.3f}"
            f"   {eff.get('mean_input_tokens_per_session', 0):>9.0f} in-tok/session"
            f"   {eff.get('successes_per_mtok_input') or 0:>6.1f} wins/Mtok"
        )
    searches = [r for r in report.admitted if r.arm == "recall"]
    if searches:
        search_rate = sum(1 for r in searches if r.memory_call_count > 0) / len(searches)
        print(f"  recall search rate: {search_rate:.3f}")
    print(f"  estimated spend: ${costs.get('estimated_usd')} ({costs['total_tokens']} tokens)")
    print(f"  artifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
