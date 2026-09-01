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
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.bare.adapter import BareAdapter
from adapters.claude_md.adapter import ClaudeMdAdapter
from adapters.fs_grep.adapter import FS_GREP_SEARCH_SENTENCE, FsGrepAdapter
from adapters.mempalace.adapter import MemPalaceAdapter
from adapters.recall.adapter import RecallAdapter
from adapters.recall_prefetch.adapter import RecallPrefetchAdapter
from harness import instructions, sandbox
from harness.abstention import declines
from harness.adapters.base import (
    ArmSpec,
    CorpusManifest,
    IngestReport,
    MemoryAdapter,
    namespace_path,
)
from harness.adapters.registry import AdapterRegistry
from harness.claude_exec import ClaudeExecConfig, run_claude_case
from harness.costs import (
    add_pricing_arguments,
    efficiency,
    pricing_from_args,
    summarize,
)
from harness.damage import CORPUS_CONDITIONS, PRESENT, Outcome, outcome_for
from harness.gate import admit_cells, with_forbidden_prefixes
from harness.instructions import refuse_shared_prompts_or_exit as refuse_shared_prompts
from harness.io import write_jsonl
from harness.placebo import length_metadata, render_placebo
from harness.prereg import assert_preregistered
from harness.runner import run_grid
from harness.tasks import discover_tasks, run_checker

#: Every arm this runner knows how to build. `protocol` and `fs_grep` joined on 2026-08-28,
#: `mempalace` on 2026-08-29, `recall_prefetch` on 2026-08-30.
#:
#: ⚠️ `oracle_memory` has an adapter and has run, and is deliberately absent. Its bundles are
#: keyed by task with NO condition, so it would supply verified evidence in `absent`, the
#: condition whose whole purpose is that the corpus does not contain the answer. It is a coherent
#: ceiling in `present` and in the single-corpus diagnostic where it ran. Admitting it here needs
#: condition-aware bundles, which is corpus work rather than wiring.
ARMS = (
    "bare", "placebo", "claude_md", "protocol", "fs_grep", "recall", "mempalace",
    "recall_prefetch",
)
DEFAULT_ARMS = ("bare", "claude_md", "recall")

#: Arms whose treatment is a memory surface, and which therefore share the memory protocol.
MEMORY_ARMS = frozenset({"fs_grep", "recall", "mempalace"})

#: Memory arms whose store THIS runner fills, in-process, before the grid. `recall` is absent
#: because its tenant is indexed out of band against the frozen corpus manifest.
SELF_INGESTING_ARMS = ("fs_grep", "mempalace")

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
    if variant in SHARED_PROTOCOL_VARIANTS:
        return instructions.compose(
            "recall", RECALL_SEARCH_SENTENCE, neutral=neutral, variant=variant
        )
    raise ValueError(f"unknown recall instruction variant {variant!r}")


#: Variants where every memory arm carries one shared protocol byte for byte, so the fairness
#: assertion is meaningful and a run is a comparison between PRODUCTS. `draft` is preregistration
#: 024's variant and differs from `protocol` in exactly one section, generated rather than written.
#: `skill` and `oneliner` are not here: they exist to reproduce runs that were never matched.
SHARED_PROTOCOL_VARIANTS = ("protocol", "draft")


def memory_instructions(variant: str, arms: tuple[str, ...], *, neutral: bool = False) -> dict[str, str]:
    """The instruction each arm carries, keyed by arm. Arms with no memory surface carry "".

    Under a shared-protocol variant every memory arm gets that protocol verbatim plus its own capped
    appendix, and the fairness assertion below is meaningful. Under ``skill`` or ``oneliner`` the
    arms are deliberately NOT matched, because those variants exist to reproduce runs that were not
    matched, and the assertion is skipped with that stated in the artifact.
    """

    shared = variant in SHARED_PROTOCOL_VARIANTS
    texts = {arm: "" for arm in arms}
    if "recall" in texts:
        texts["recall"] = recall_instruction(variant, neutral=neutral)
    if "fs_grep" in texts:
        texts["fs_grep"] = (
            FsGrepAdapter.shared_instruction(neutral=neutral, variant=variant)
            if shared
            # The historical sentence, so a `skill`/`oneliner` rerun reproduces the old asymmetry
            # rather than half-fixing it and being comparable to neither.
            else instructions.compose("fs_grep", FS_GREP_SEARCH_SENTENCE, neutral=neutral)
        )
    if "mempalace" in texts:
        # No historical variant to reproduce: this arm has never run, so it always carries a
        # shared protocol. Under `skill`/`oneliner` that leaves it matched against an
        # unmatched recall arm, which `instruction_manifest` publishes rather than hides.
        texts["mempalace"] = MemPalaceAdapter.shared_instruction(
            neutral=neutral, variant=variant if shared else "protocol"
        )
    if "protocol" in texts:
        texts["protocol"] = instructions.compose(
            "protocol",
            PROTOCOL_SEARCH_SENTENCE,
            neutral=neutral,
            variant=variant if shared else "protocol",
        )
    if shared:
        instructions.assert_shared_protocol(texts, neutral=neutral, variant=variant)
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

    # Derived, not listed: this loop used to name ("protocol", "fs_grep", "recall") literally,
    # so an arm added to ARMS and to `memory_instructions` still got no bundle here and fell
    # back to a bare prompt with its instruction silently dropped.
    for arm in sorted(set(texts) - {"bare", "claude_md", "placebo"}):
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
    if arm == "mempalace":
        return MemPalaceAdapter(staging, static, instruction=texts.get("mempalace") or None)
    if arm == "recall_prefetch":
        # Wraps a recall adapter and runs the same published search from the HARNESS side, so it
        # is condition-aware for free: it delegates to whichever tenant the condition serves. The
        # gap between this arm and `recall` is the agent's DECISION to search, which the four
        # adversarial conditions cannot otherwise separate from retrieval quality -- and on this
        # feed retrieval is saturated (voyage hit@10 = 1.000), so that separation is the only
        # place a difference can come from.
        return RecallPrefetchAdapter(
            RecallAdapter(staging, static, instruction=texts.get("recall") or None),
            staging,
            static,
        )
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
    abstained, marker = declines(response)
    if condition == PRESENT:
        # `present` plants nothing, so there is no wrong fact for a detector to find and
        # `detect_damage` refuses the condition outright. The cell still needs its outcome and,
        # more importantly, its ABSTENTION flag: on `present` a decline is the missed-opportunity
        # cell that the four adversarial conditions cannot express, which is the entire reason
        # this condition exists. Routing it through the detector would raise ValueError on the
        # first cell of the run.
        return {
            "condition": condition,
            "outcome": (Outcome.SOLVED if checker_ok else Outcome.NEUTRAL_FAILURE).value,
            "damage_reason": "no damage detector runs under `present`: nothing is planted",
            "abstained": abstained,
            "abstain_marker": marker,
        }
    outcome, reason = outcome_for(
        task.path, workdir, task.oracle_dir, condition, checker_ok, verdict
    )
    return {
        "condition": condition,
        "outcome": outcome.value,
        "damage_reason": reason,
        "abstained": abstained,
        "abstain_marker": marker,
    }



def _refuse_a_dirty_work_root(work_root: Path, run_id: str) -> None:
    """Stop before the first session if this run id has already been used here.

    `sandbox.restore` refuses a destination that already has contents, which is right: a sandbox
    carrying another session's files is not a fixture. But that refusal arrives PER CELL, is caught
    as "the session did not complete", and lands as a DISCARDED CELL. So a re-run under a run id
    whose work root survives loses exactly the cells the previous attempt reached, silently, and
    the admission report blames the sessions.

    Measured 2026-08-29 on `abstention-002`: two aborted launches left sandboxes for eight cells,
    and the third launch discarded all eight. 22 of 30 cells admitted on `absent`, against a 6%
    discard rate in `abstention-001`, and every reason in `admission.json` was a FileExistsError
    naming a path from a run that no longer existed.

    A partly-used work root is an operator error, not a data problem, so it is refused up front and
    named. Deleting it here would be worse: those directories are the only surviving trace of what
    an aborted run actually did.
    """

    work = work_root / "work"
    if not work.is_dir():
        return
    existing = sorted(p.name for p in work.iterdir() if p.is_dir())
    if not existing:
        return
    shown = existing[:5]
    more = "..." if len(existing) > 5 else ""
    raise SystemExit(
        f"work root for run id {run_id!r} already holds sandboxes for {len(existing)} task(s): "
        f"{shown}{more}\n"
        f"  {work}\n"
        f"Every cell whose sandbox survives there would be DISCARDED, not re-run, because restore "
        f"refuses a destination with contents and the admission gate reads that as a session that "
        f"did not complete. Move or delete that directory, or choose a different --run-id. It is "
        f"not removed automatically: it is the only trace of what the earlier attempt did."
    )


#: Task-id prefixes an ordinary run measures when `--tasks` is not given.
#:
#: ⛔ This was a bare `startswith("ts-")` until 2026-08-30, and that single string is why the
#: library stayed monotonic in practice. `xs-*`, the three cross-session synthesis tasks, have
#: never appeared in a grid: they were authored, they pass their own tests, and the runner has
#: skipped them since they were written. Nobody decided that. A string comparison decided it.
#:
#: ⚠️ **Nothing joins this tuple without a preregistration.** Admitting a class changes what every
#: default run measures, and the preregistered runs did not contain it, so it is a measurement
#: decision and not a wiring repair. `tests/test_pilot_subset.py` fired on the first attempt to
#: add `fa-` here and was right to.
GRID_PREFIXES = ("ts-",)

#: Prefixes `--tasks` may name. Wider than the default grid on purpose: a new class has to be
#: runnable before anyone can calibrate it, and calibrating it is the evidence a preregistration
#: would rest on. Selecting one is explicit and leaves the default grid alone.
SELECTABLE_PREFIXES = ("ts-", "fa-")

#: Classes in neither, with the reason, so an absence is a decision on the record rather than an
#: oversight.
EXCLUDED_PREFIXES = {
    "xs-": (
        "cross-session synthesis; needs a corpus shape the grid does not assemble, and admitting "
        "it changes what every run measures"
    ),
}


def diagnostic_metadata(spec: Any) -> dict[str, Any]:
    """The adapter's `memory_diagnostic`, to be merged into the session record.

    ⛔ Without this the admission gate discards EVERY cell of EVERY condition.

    A diagnostic adapter returns `AdmissionSignal(metadata={"diagnostic_kind": <arm>})` and puts a
    matching `memory_diagnostic` on its `ArmSpec`. `harness.gate._check_diagnostic` compares the
    two and refuses when they disagree, and a cell is admitted only when EVERY arm is admitted, so
    one unstamped arm voids the whole grid.

    `scripts/diagnostic.py` copied the spec metadata across and this runner never did, which is why
    `recall_prefetch` worked in `diagnostic-010` (70 of 72 cells admitted) and destroyed
    `official-002`: 360 sessions run, 44 of 60 prefetch sessions successful, and **0 cells
    admitted**, all 60 discarded with
    `diagnostic arm 'recall_prefetch' expected memory treatment 'recall_prefetch', got None`.

    ⚠️ Only `memory_diagnostic` is carried, never the whole spec metadata. The adapter also sets
    `prompt_sha256`, and the runner computes that itself from the file it actually used; a blanket
    merge would silently let the adapter's value win.
    """
    metadata = getattr(spec, "metadata", None)
    if isinstance(metadata, Mapping) and "memory_diagnostic" in metadata:
        return {"memory_diagnostic": metadata["memory_diagnostic"]}
    return {}


def block_concurrency() -> int:
    """How many (task, seed) cells run at once. `AMB_BLOCK_CONCURRENCY`, default 1.

    Every arm of a cell already runs concurrently (`arm_concurrency` is None), so the default of 1
    still puts one session per arm in flight. This multiplies that, and the multiplier is the whole
    wall clock of a run: 2,555 sessions at seven-in-flight is hours.

    ⛔ **The ceiling is host memory, and exceeding it does not raise, it DELETES DATA.** Three arms
    spawn a per-session MCP server. Starve the host and the server never answers `initialize`,
    Claude Code reports the server failed with an EMPTY error list, the session runs with no memory
    tools, the model answers from its own knowledge, and the record looks perfectly ordinary. The
    admission gate then discards the cell, correctly. So contention does not produce errors, it
    produces missing cells, and a run can be quietly hollowed out while every log looks clean.
    Measured in `diagnostic-002`: 421 MB free, and the recall arm failed nearly every session after
    the first six.

    ⚠️ It also widens the STARTUP race, which is the documented binding constraint on grid width.
    The server takes ~12.3s to answer, `pilot-004` lost 8 of 72 recall sessions to it (11.1%), and
    a cell is admitted only when EVERY arm wired: at that rate five memory servers admit a cell
    with probability 0.889^5 = 0.55 against a 95% admission rule. `harness/memory_startup.py`
    probes and retries, which is what makes raising this survivable rather than safe.

    So this is bounded deliberately, and the bound is memory per concurrent memory-arm server
    rather than CPU: the sessions are waiting on an API, not computing.
    """
    raw = os.environ.get("AMB_BLOCK_CONCURRENCY", "").strip()
    if not raw:
        return 1
    try:
        value = int(raw)
    except ValueError:
        print(f"[pilot] AMB_BLOCK_CONCURRENCY={raw!r} is not an integer; using 1", flush=True)
        return 1
    if value < 1:
        print(f"[pilot] AMB_BLOCK_CONCURRENCY={value} is not positive; using 1", flush=True)
        return 1
    # A hard ceiling, not advice. Three memory arms at roughly 815 MB per server means 8 cells is
    # ~20 GB of servers alone, which is the shape that produced the starvation above.
    if value > 8:
        print(f"[pilot] AMB_BLOCK_CONCURRENCY={value} exceeds the ceiling; using 8", flush=True)
        return 8
    return value


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
        choices=("oneliner", "skill", "protocol", "draft"),
        default="oneliner",
        help="which instruction the memory arms carry; recorded in the artifacts. `protocol` and "
        "`draft` are the matched variants: each gives every memory arm one shared protocol plus "
        "that product's own capped appendix. `draft` is preregistration 024's variant and differs "
        "from `protocol` in exactly one section, `## How to search`, telling the agent to search "
        "with the text it is about to write rather than by decomposing the task into operations; "
        "it is generated by scripts/build_draft_protocol.py so the one-variable claim is checkable. "
        "`skill` reproduces pilot-002 through pilot-004, in which the recall arm carried 5,428 "
        "characters and no other arm carried more than 231.",
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
        choices=("", *CORPUS_CONDITIONS),
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
    add_pricing_arguments(parser)
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
    if "protocol" in run_arms and args.memory_instruction not in SHARED_PROTOCOL_VARIANTS:
        raise SystemExit(
            "the `protocol` arm is the instruction-only control for the shared memory protocol, "
            f"so it is only meaningful with --memory-instruction in {SHARED_PROTOCOL_VARIANTS}. "
            "With `skill` or `oneliner` it would carry a different instruction from the memory "
            "arms it exists to be compared against."
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

    # The default grid, and the wider set a --tasks subset may name. Keeping these apart is what
    # lets a new class be calibrated without silently changing what an ordinary run measures.
    prefixes = SELECTABLE_PREFIXES if args.tasks else GRID_PREFIXES
    tasks = [task for task in discover_tasks() if task.task_id.startswith(prefixes)]
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
    _refuse_a_dirty_work_root(work_root, args.run_id)
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
    self_ingesting = [arm for arm in SELF_INGESTING_ARMS if arm in run_arms]
    if self_ingesting:
        corpus = CorpusManifest.load(corpus_root)
        for arm in self_ingesting:
            print(f"[ingest] {arm} from {corpus_root}", flush=True)
            report = registry.get(arm).ingest(corpus, args.namespace)
            print(
                f"[ingest] {arm}: {report.items_stored} item(s) from "
                f"{report.sessions_offered} session(s)",
                flush=True,
            )
            ingest_reports.append(report)

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
    # `--namespace` is a CLI argument and this path is handed to the fs_grep arm as its
    # store. Validated here for the same reason the adapter validates its own join.
    fs_grep_memory = (
        namespace_path(staging, args.namespace, "memory") if "fs_grep" in run_arms
        else None
    )

    async def runner(row, arm):
        task_id, seed = str(row["task_id"]), int(row["seed"])
        workdir = work_root / "work" / task_id / f"s{seed}" / arm
        overlay = fs_grep_memory if arm == "fs_grep" else None
        digest = sandbox.restore(task_id, workdir, overlay=overlay)
        record = await run_claude_case(row, arm, config_for(task_id, seed, arm, workdir))
        ok, verdict = run_checker(by_id[task_id], workdir)
        spec = specs[(task_id, arm)]
        prompt_file = spec.append_system_prompt_file

        # ⛔ Carry the adapter's diagnostic metadata into the RECORD, or the admission gate
        # discards every cell of every condition.
        #
        # A diagnostic adapter returns `AdmissionSignal(metadata={"diagnostic_kind": <arm>})` and
        # puts the matching `memory_diagnostic` on its `ArmSpec`. `harness.gate._check_diagnostic`
        # compares the two and refuses when they disagree. `scripts/diagnostic.py` copied the spec
        # metadata across; this runner never did, so `recall_prefetch` sessions RAN, SUCCEEDED, and
        # were then discarded to a cell with
        #     diagnostic arm 'recall_prefetch' expected memory treatment 'recall_prefetch', got None
        # and because a cell is admitted only when EVERY arm is admitted, one unstamped arm voids
        # the entire grid. Measured 2026-08-31 on official-002: 360 sessions run, 0 cells admitted,
        # 60 of 60 discarded, all attributed to recall_prefetch.
        #
        # ⚠️ Only `memory_diagnostic` is carried, not the whole spec metadata: the adapter also
        # sets `prompt_sha256`, which this runner computes itself from the file it actually used,
        # and a blanket merge would let the adapter's value win.
        diagnostic_extra = diagnostic_metadata(spec)

        # Classify HERE, not in the analysis. A damage detector needs the finished working tree,
        # and by the time anything reads records.jsonl the sandbox is gone. Without this the
        # outcome could only be re-derived by re-running the grid.
        condition_extra = classify_cell(
            by_id[task_id], workdir, args.condition, ok, verdict, record.response or ""
        )

        extra = {
            "checker": verdict,
            **condition_extra,
            **diagnostic_extra,
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
    records = await run_grid(rows, run_arms, runner, block_concurrency=block_concurrency())
    wall_min = (time.monotonic() - started) / 60

    write_jsonl(run_dir / "records.final.jsonl", records)
    report = admit_cells(records, signals, required_arms=run_arms)
    (run_dir / "admission.json").write_text(
        json.dumps(report.summary(), indent=2), encoding="utf-8"
    )
    pricing = pricing_from_args(args, model=args.model, source="https://openrouter.ai/api/v1/models")
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
