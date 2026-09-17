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
import shutil
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
from adapters.cachly.adapter import CachlyAdapter
from adapters.claude_md.adapter import ClaudeMdAdapter
from adapters.claude_mem.adapter import ClaudeMemAdapter
from adapters.fs_grep.adapter import FS_GREP_SEARCH_SENTENCE, FsGrepAdapter

try:
    from adapters.graphiti.adapter import GraphitiAdapter
except ModuleNotFoundError as exc:
    if exc.name not in {"adapters.graphiti", "adapters.graphiti.adapter"}:
        raise
    GraphitiAdapter = None
from adapters.mempalace.adapter import MemPalaceAdapter
from adapters.oracle_memory.adapter import OracleMemoryAdapter
from adapters.recall.adapter import RecallAdapter
from adapters.recall_checkpoint.adapter import (
    RecallGraphFullToolsCheckpointAdapter,
    RecallGraphFullToolsCheckpointPlaceboAdapter,
)
from adapters.recall_checkpoint.hook import (
    HIT_TEXT_LIMIT as CHECKPOINT_HIT_TEXT_LIMIT,
)
from adapters.recall_checkpoint.hook import (
    MARKER as CHECKPOINT_MARKER,
)
from adapters.recall_checkpoint.hook import (
    MAX_HITS as CHECKPOINT_MAX_HITS,
)
from adapters.recall_checkpoint.hook import (
    QUERY_LIMIT as CHECKPOINT_QUERY_LIMIT,
)
from adapters.recall_checkpoint.hook import (
    REASON_LIMIT as CHECKPOINT_REASON_LIMIT,
)
from adapters.recall_checkpoint.hook import (
    CheckpointError,
    is_mutation_candidate,
    parse_checkpoint_marker,
)
from adapters.recall_graph_fulltools.adapter import (
    RecallGraphFullToolsAdapter,
    RecallGraphFullToolsDecisionProtocolAdapter,
    RecallGraphFullToolsProtocolAdapter,
    RecallGraphFullToolsQualityGateAdapter,
)
from adapters.recall_graph_rerank.adapter import RecallGraphRerankAdapter
from adapters.recall_prefetch.adapter import RecallPrefetchAdapter
from adapters.recall_prompt_time.adapter import RecallGraphFullToolsPromptTimeAdapter
from adapters.recall_rerank.adapter import RecallRerankAdapter
from adapters.supermemory.adapter import SupermemoryAdapter
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
from harness.adjudication import (
    Challenge,
    RuntimeEventLog,
    adjudicate_run,
    admission_signal_snapshot,
    issue_challenge,
    json_digest,
    load_private_signer,
    tree_digest,
)
from harness.broker import SessionCapabilityIssuer, probe_jsonrpc_endpoint
from harness.claude_exec import ClaudeExecConfig
from harness.costs import (
    add_pricing_arguments,
    efficiency,
    pricing_from_args,
    summarize,
)
from harness.damage import CORPUS_CONDITIONS, PRESENT, Outcome, outcome_for
from harness.decision_trace import (
    DECISION_OUTPUT_INSTRUCTION,
    DECISION_OUTPUT_SCHEMA,
    DECISION_STAGE_INSTRUCTION,
    STAGED_DECISION_OUTPUT_SCHEMA,
    with_decision_output_instruction,
)
from harness.frozen_manifest import FrozenEvaluationManifest
from harness.gate import admit_cells, with_forbidden_prefixes
from harness.instructions import refuse_shared_prompts_or_exit as refuse_shared_prompts
from harness.io import read_jsonl
from harness.isolation import (
    default_participant_policy,
    run_isolated_checker,
    run_isolated_claude_case,
)
from harness.memory_bundles import MemoryBundleCatalog
from harness.placebo import length_metadata, render_placebo
from harness.prereg import assert_preregistered
from harness.privacy import load_provider_policy, provider_policy_metadata, write_public_jsonl
from harness.runner import run_grid, run_sequences
from harness.sequence_plan import load_plan_file
from harness.sequence_preflight import validate_sequence_evaluation
from harness.sequence_validation import validate_plan
from harness.tasks import discover_tasks
from scripts.validate_run_setup import validate as validate_setup

#: Every arm this runner knows how to build. `protocol` and `fs_grep` joined on 2026-08-28,
#: `mempalace` on 2026-08-29, `recall_prefetch` on 2026-08-30, `recall_rerank` and `cachly` on
#: 2026-09-02.
#:
#: `recall_rerank` is `recall` with its Voyage reranker on, and it belongs in the SAME grid rather
#: than in a second run: paired inside one grid the corpus feed, the model, the suite and the
#: admitted set are held constant by construction, where across two runs none of them are.
#:
#: ⚠️ `oracle_memory` has an adapter and has run, and is admitted only for the frozen
#: official-016 superseded ceiling pair. Its bundles are
#: keyed by task with NO condition, so it would supply verified evidence in `absent`, the
#: condition whose whole purpose is that the corpus does not contain the answer. It is a coherent
#: ceiling in `present` and in the single-corpus diagnostic where it ran. Admitting it here needs
#: condition-aware bundles, which is corpus work rather than wiring.
ARMS = (
    "bare", "placebo", "claude_md", "protocol", "fs_grep", "recall", "recall_rerank",
    "recall_graph_rerank", "recall_graph_fulltools", "recall_graph_fulltools_protocol",
    "recall_graph_fulltools_quality_gate", "recall_graph_fulltools_decision_protocol",
    "recall_graph_fulltools_checkpoint_placebo", "recall_graph_fulltools_checkpoint",
    "recall_graph_fulltools_prompt_time",
    "mempalace", "recall_prefetch", "oracle_memory", "cachly", "graphiti", "supermemory",
    "claude_mem",
)
DEFAULT_ARMS = ("bare", "claude_md", "recall")
RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM = "recall_graph_fulltools_protocol"
RECALL_GRAPH_FULLTOOLS_QUALITY_GATE_ARM = "recall_graph_fulltools_quality_gate"
RECALL_GRAPH_FULLTOOLS_DECISION_PROTOCOL_ARM = "recall_graph_fulltools_decision_protocol"
RECALL_GRAPH_FULLTOOLS_CHECKPOINT_PLACEBO_ARM = "recall_graph_fulltools_checkpoint_placebo"
RECALL_GRAPH_FULLTOOLS_CHECKPOINT_ARM = "recall_graph_fulltools_checkpoint"
RECALL_GRAPH_FULLTOOLS_PROMPT_TIME_ARM = "recall_graph_fulltools_prompt_time"
RECALL_GRAPH_FULLTOOLS_PAIRED_ARMS = (
    RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM,
    RECALL_GRAPH_FULLTOOLS_QUALITY_GATE_ARM,
)
RECALL_GRAPH_FULLTOOLS_DECISION_PAIRED_ARMS = (
    RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM,
    RECALL_GRAPH_FULLTOOLS_DECISION_PROTOCOL_ARM,
)
RECALL_ORACLE_CEILING_PAIRED_ARMS = (
    RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM,
    "oracle_memory",
)
RECALL_PREMUTATION_CHECKPOINT_PAIRED_ARMS = (
    RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM,
    RECALL_GRAPH_FULLTOOLS_CHECKPOINT_PLACEBO_ARM,
    RECALL_GRAPH_FULLTOOLS_CHECKPOINT_ARM,
)
RECALL_PROMPT_TIME_PAIRED_ARMS = (
    RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM,
    RECALL_GRAPH_FULLTOOLS_PROMPT_TIME_ARM,
)
RECALL_ORACLE_CEILING_TASKS = frozenset(
    {
        "ts-base36-id",
        "ts-bom-merge",
        "ts-golden-regen",
        "ts-ignore-gen",
        "ts-legacy-hash",
        "ts-mig-name",
        "ts-schema-additive",
        "ts-semver-pin",
        "ts-tz-utc",
    }
)
RECALL_ORACLE_CEILING_CATALOG_SHA256 = (
    "322cd2331c8b1c6ed0e01eb293f6dd562088a016c6b31c25d304efe46ef5dad6"
)
RECALL_ORACLE_SOURCE_SHA256 = (
    "65592ceb95c07f00d5b4c9204b4b733875124034eff2fd4bdb903c32cf9629cb"
)
RECALL_GRAPH_FULLTOOLS_CONTROL_SHA256 = (
    "aae2f2cf6fe67cac3998b1692d9173ef9ae7edcbe3263053d36025e77f2dc7d8"
)
RECALL_GRAPH_FULLTOOLS_QUALITY_GATE_SHA256 = (
    "fb8295ddf00d2b4573c7f622cc2086688e418124d8cb294de972ae18cd1a5a07"
)
RECALL_GRAPH_FULLTOOLS_DECISION_PROTOCOL_SHA256 = (
    "a3ccb2af267521cc71886d999abb81cf39a29d97e6aebfd1ed5672b8022cb907"
)
RECALL_GRAPH_FULLTOOLS_ARMS = frozenset(
    {
        "recall_graph_fulltools",
        *RECALL_GRAPH_FULLTOOLS_PAIRED_ARMS,
        *RECALL_GRAPH_FULLTOOLS_DECISION_PAIRED_ARMS,
        *RECALL_PREMUTATION_CHECKPOINT_PAIRED_ARMS,
        *RECALL_PROMPT_TIME_PAIRED_ARMS,
    }
)
RECALL_ARMS = frozenset(
    {"recall", "recall_rerank", "recall_graph_rerank", *RECALL_GRAPH_FULLTOOLS_ARMS}
)

#: Arms whose treatment is a memory surface, and which therefore share the memory protocol.
MEMORY_ARMS = frozenset(
    {
        "fs_grep", "recall", "recall_rerank", "recall_graph_rerank",
        *RECALL_GRAPH_FULLTOOLS_ARMS,
        "mempalace", "cachly", "graphiti",
        "supermemory", "claude_mem",
    }
)

#: Memory arms whose store THIS runner fills, in-process, before the grid. `recall` is absent
#: because its tenant is indexed out of band against the frozen corpus manifest.
SELF_INGESTING_ARMS = (
    "fs_grep", "mempalace", "cachly", "graphiti", "supermemory", "claude_mem"
)

#: Arms that are a static system-prompt file and nothing else.
STATIC_ARMS = frozenset({"placebo", "claude_md", "protocol"})

BASE_TOOLS = ("Read", "Grep", "Glob", "Bash", "Write", "Edit")
DENIED_TOOLS = ("Bash(docker:*)", "Bash(docker-compose:*)")
RECALL_CONFIG = json.loads(
    (REPO / "adapters" / "recall" / "config.frozen.json").read_text(encoding="utf-8")
)
RECALL_GRAPH_CONFIG = json.loads(
    (REPO / "adapters" / "recall_graph_rerank" / "config.frozen.json").read_text(
        encoding="utf-8"
    )
)
RECALL_GRAPH_FULLTOOLS_CONFIG = json.loads(
    (REPO / "adapters" / "recall_graph_fulltools" / "config.frozen.json").read_text(
        encoding="utf-8"
    )
)
RECALL_PREFIX = str(RECALL_CONFIG["tool_prefix"])
CLAUDE_MEM_CONFIG = json.loads(
    (REPO / "adapters" / "claude_mem" / "config.frozen.json").read_text(encoding="utf-8")
)
CLAUDE_MEM_PREFIX = str(CLAUDE_MEM_CONFIG["tool_prefix"])
GRAPHITI_CONFIG_PATH = REPO / "adapters" / "graphiti" / "config.frozen.json"
GRAPHITI_CONFIG = (
    json.loads(GRAPHITI_CONFIG_PATH.read_text(encoding="utf-8"))
    if GRAPHITI_CONFIG_PATH.is_file()
    else {}
)
GRAPHITI_PREFIX = str(GRAPHITI_CONFIG.get("tool_prefix", "mcp__graphiti__"))
GENERIC_RULES = (
    "# Project notes\n\n"
    "You are working in this repository. Keep changes small and leave the tree clean.\n\n"
)

#: The recall arm's one line in the shared protocol's slot.
RECALL_SEARCH_SENTENCE = (
    "This project keeps a searchable memory of past work sessions; search it with the "
    f"`{RECALL_PREFIX}recall_search` tool before acting."
)

RECALL_GRAPH_SENTENCE = (
    "This arm measures RE-call graph retrieval; when memory is relevant, call the "
    f"`{RECALL_PREFIX}recall_reasoning_query` tool with `graph_expansion=one_hop` and "
    "`expand_retrieval=false` before acting. The ordinary recall_search tool does not exercise "
    "the graph path."
)

RECALL_GRAPH_FULLTOOLS_SENTENCE = (
    "This arm measures RE-call graph retrieval. Before acting in every session, call the "
    f"`{RECALL_PREFIX}recall_reasoning_query` tool with `graph_expansion=one_hop` and "
    "`expand_retrieval=false`, even if the task appears straightforward or memory seems "
    "irrelevant. This graph call is the required first memory operation. After it returns, use "
    "the available read and navigation tools when useful; do not mutate or ingest the memory "
    "store during the coding task."
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


def recall_graph_instruction(variant: str, *, neutral: bool = False) -> str:
    """The graph arm's route-specific instruction.

    A normal ``recall_search`` call cannot exercise graph expansion. The route is therefore named
    explicitly and its two frozen arguments are stated in the arm instruction. This is an intended
    treatment difference, recorded in the graph arm config and preregistration, rather than a
    hidden prompt drift.
    """

    if variant == "oneliner":
        return str(RECALL_GRAPH_CONFIG["instruction"]).format(
            server=RECALL_GRAPH_CONFIG["server_name"],
            tool=f"{RECALL_PREFIX}recall_reasoning_query",
        )
    if variant == "skill":
        text = (REPO / "adapters" / "recall" / "skill.md").read_text(encoding="utf-8")
        if text.startswith("---"):
            text = text.split("---", 2)[2]
        return text.replace("recall_search", "recall_reasoning_query").strip() + "\n\n" + RECALL_GRAPH_SENTENCE
    if variant in SHARED_PROTOCOL_VARIANTS:
        return instructions.compose(
            "recall_graph_rerank", RECALL_GRAPH_SENTENCE, neutral=neutral, variant=variant
        )
    raise ValueError(f"unknown recall instruction variant {variant!r}")


def recall_graph_fulltools_instruction(variant: str, *, neutral: bool = False) -> str:
    """The tested skill prompt plus an unconditional graph-first requirement."""

    if variant == "oneliner":
        return str(RECALL_GRAPH_FULLTOOLS_CONFIG["instruction"]).format(
            server=RECALL_GRAPH_FULLTOOLS_CONFIG["server_name"],
            tool=f"{RECALL_PREFIX}recall_reasoning_query",
        )
    if variant == "skill":
        text = (REPO / "adapters" / "recall" / "skill.md").read_text(encoding="utf-8")
        if text.startswith("---"):
            text = text.split("---", 2)[2]
        return text.strip() + "\n\n" + RECALL_GRAPH_FULLTOOLS_SENTENCE + "\n"
    if variant == "quality":
        return (REPO / "adapters" / "recall" / "skill-quality.md").read_text(
            encoding="utf-8"
        ).strip()
    if variant in SHARED_PROTOCOL_VARIANTS:
        return instructions.compose(
            "recall_graph_fulltools",
            RECALL_GRAPH_FULLTOOLS_SENTENCE,
            neutral=neutral,
            variant=variant,
        )
    raise ValueError(f"unknown recall instruction variant {variant!r}")


def recall_graph_quality_gate_instruction() -> str:
    """The exact official-012 control followed only by official-014's frozen appendix."""

    control = recall_graph_fulltools_instruction("protocol")
    appendix = (REPO / "adapters" / "recall" / "skill-quality-gate.md").read_text(
        encoding="utf-8"
    ).strip()
    return control + "\n" + appendix


def quality_gate_pair_metadata(texts: Mapping[str, str]) -> dict[str, Any]:
    """Prove the treatment is exactly the frozen control plus one frozen appendix."""

    control = texts.get(RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM, "")
    treatment = texts.get(RECALL_GRAPH_FULLTOOLS_QUALITY_GATE_ARM, "")
    # The control already ends with one newline. One additional newline creates the blank line
    # before the appendix while preserving every control byte as the exact treatment prefix.
    separator = "\n"
    prefix_matches = treatment.startswith(control + separator)
    appendix = treatment.removeprefix(control + separator) if prefix_matches else ""
    return {
        "arms": list(RECALL_GRAPH_FULLTOOLS_PAIRED_ARMS),
        "control_bytes": len(control.encode("utf-8")),
        "control_sha256": hashlib.sha256(control.encode("utf-8")).hexdigest(),
        "treatment_bytes": len(treatment.encode("utf-8")),
        "treatment_sha256": hashlib.sha256(treatment.encode("utf-8")).hexdigest(),
        "treatment_prefix_matches_control": prefix_matches,
        "appendix_bytes": len(appendix.encode("utf-8")),
        "appendix_sha256": hashlib.sha256(appendix.encode("utf-8")).hexdigest(),
    }


def recall_decision_protocol_instruction() -> str:
    """Return official-015's exact preregistered search-first protocol."""

    return (REPO / "adapters" / "recall" / "skill-decision-protocol.md").read_text(
        encoding="utf-8"
    )


def decision_protocol_pair_metadata(texts: Mapping[str, str]) -> dict[str, Any]:
    """Record both complete frozen instructions for official-015."""

    control = texts.get(RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM, "")
    treatment = texts.get(RECALL_GRAPH_FULLTOOLS_DECISION_PROTOCOL_ARM, "")
    return {
        "arms": list(RECALL_GRAPH_FULLTOOLS_DECISION_PAIRED_ARMS),
        "control_bytes": len(control.encode("utf-8")),
        "control_sha256": hashlib.sha256(control.encode("utf-8")).hexdigest(),
        "treatment_bytes": len(treatment.encode("utf-8")),
        "treatment_sha256": hashlib.sha256(treatment.encode("utf-8")).hexdigest(),
    }


#: Variants where every memory arm carries one shared protocol byte for byte, so the fairness
#: assertion is meaningful and a run is a comparison between PRODUCTS. `draft` is preregistration
#: 024's variant and differs from `protocol` in exactly one section, generated rather than written.
#: `skill` and `oneliner` are not here: they exist to reproduce runs that were never matched.
SHARED_PROTOCOL_VARIANTS = ("protocol", "draft")
QUALITY_GATE_PAIRED_VARIANT = "quality_gate_paired"
DECISION_PROTOCOL_PAIRED_VARIANT = "decision_protocol_paired"
ORACLE_CEILING_PAIRED_VARIANT = "oracle_ceiling_paired"
PREMUTATION_CHECKPOINT_PAIRED_VARIANT = "premutation_checkpoint_paired"
PROMPT_TIME_PAIRED_VARIANT = "prompt_time_auto_retrieval"


def validate_quality_gate_pair(variant: str, arms: tuple[str, ...]) -> None:
    """Keep the preregistered treatment from leaking into another roster."""

    if variant != QUALITY_GATE_PAIRED_VARIANT:
        return
    if len(arms) != 2 or set(arms) != set(RECALL_GRAPH_FULLTOOLS_PAIRED_ARMS):
        raise ValueError(
            f"{QUALITY_GATE_PAIRED_VARIANT!r} requires exactly "
            f"{RECALL_GRAPH_FULLTOOLS_PAIRED_ARMS}, got {arms}"
        )


def validate_decision_protocol_pair(variant: str, arms: tuple[str, ...]) -> None:
    """Keep official-015's whole-skill treatment inside its frozen paired roster."""

    if variant != DECISION_PROTOCOL_PAIRED_VARIANT:
        return
    if len(arms) != 2 or set(arms) != set(RECALL_GRAPH_FULLTOOLS_DECISION_PAIRED_ARMS):
        raise ValueError(
            f"{DECISION_PROTOCOL_PAIRED_VARIANT!r} requires exactly "
            f"{RECALL_GRAPH_FULLTOOLS_DECISION_PAIRED_ARMS}, got {arms}"
        )


def validate_oracle_ceiling_pair(
    variant: str,
    arms: tuple[str, ...],
    tasks: list[Any] | tuple[Any, ...] | None = None,
    condition: str | None = None,
) -> None:
    """Keep official-016 inside its frozen superseded roster."""

    if variant != ORACLE_CEILING_PAIRED_VARIANT:
        return
    if tuple(arms) != RECALL_ORACLE_CEILING_PAIRED_ARMS:
        raise ValueError(
            f"{ORACLE_CEILING_PAIRED_VARIANT!r} requires exactly "
            f"{RECALL_ORACLE_CEILING_PAIRED_ARMS} in that order, got {arms}"
        )
    if condition is not None and condition != "superseded":
        raise ValueError(
            f"{ORACLE_CEILING_PAIRED_VARIANT!r} requires condition 'superseded', "
            f"got {condition!r}"
        )
    if tasks is not None:
        observed = [str(task.task_id) for task in tasks]
        if len(observed) != len(RECALL_ORACLE_CEILING_TASKS) or set(observed) != set(
            RECALL_ORACLE_CEILING_TASKS
        ):
            raise ValueError(
                f"{ORACLE_CEILING_PAIRED_VARIANT!r} requires exactly the frozen nine tasks, "
                f"got {observed}"
            )


def validate_premutation_checkpoint_pair(
    variant: str,
    arms: tuple[str, ...],
    tasks: list[Any] | tuple[Any, ...] | None = None,
    condition: str | None = None,
) -> None:
    """Keep official-017 inside its frozen three-arm superseded roster."""

    if variant != PREMUTATION_CHECKPOINT_PAIRED_VARIANT:
        return
    if tuple(arms) != RECALL_PREMUTATION_CHECKPOINT_PAIRED_ARMS:
        raise ValueError(
            f"{PREMUTATION_CHECKPOINT_PAIRED_VARIANT!r} requires exactly "
            f"{RECALL_PREMUTATION_CHECKPOINT_PAIRED_ARMS} in that order, got {arms}"
        )
    if condition is not None and condition != "superseded":
        raise ValueError(
            f"{PREMUTATION_CHECKPOINT_PAIRED_VARIANT!r} requires condition 'superseded', "
            f"got {condition!r}"
        )
    if tasks is not None:
        observed = [str(task.task_id) for task in tasks]
        if len(observed) != len(RECALL_ORACLE_CEILING_TASKS) or set(observed) != set(
            RECALL_ORACLE_CEILING_TASKS
        ):
            raise ValueError(
                f"{PREMUTATION_CHECKPOINT_PAIRED_VARIANT!r} requires exactly the frozen nine "
                f"tasks, got {observed}"
            )


def validate_prompt_time_pair(variant: str, arms: tuple[str, ...]) -> None:
    """Keep official-019's hook treatment inside its exact paired roster."""

    if variant != PROMPT_TIME_PAIRED_VARIANT:
        return
    if tuple(arms) != RECALL_PROMPT_TIME_PAIRED_ARMS:
        raise ValueError(
            f"{PROMPT_TIME_PAIRED_VARIANT!r} requires exactly "
            f"{RECALL_PROMPT_TIME_PAIRED_ARMS} in that order, got {arms}"
        )


def load_oracle_ceiling_catalog(
    corpus_root: Path, tasks: list[Any] | tuple[Any, ...]
) -> MemoryBundleCatalog:
    """Load and validate only official-016's preregistered oracle bundles."""

    source = REPO / "corpus" / "oracle_memory" / "bundles.jsonl"
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_sha256 != RECALL_ORACLE_SOURCE_SHA256:
        raise ValueError(
            "oracle bundle source differs from the official-016 preregistration: "
            f"expected {RECALL_ORACLE_SOURCE_SHA256}, got {source_sha256}"
        )
    corpus = CorpusManifest.load(corpus_root)
    catalog = MemoryBundleCatalog.load(
        source.parent,
        corpus,
        tasks,
        include_task_ids=RECALL_ORACLE_CEILING_TASKS,
    )
    if catalog.digest != RECALL_ORACLE_CEILING_CATALOG_SHA256:
        raise ValueError(
            "selected oracle catalog differs from the official-016 preregistration: "
            f"expected {RECALL_ORACLE_CEILING_CATALOG_SHA256}, got {catalog.digest}"
        )
    return catalog


def oracle_ceiling_pair_metadata(
    texts: dict[str, str], catalog: MemoryBundleCatalog
) -> dict[str, Any]:
    """The frozen official-016 treatment identity recorded before the grid."""

    control = texts.get(RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM, "")
    oracle = texts.get("oracle_memory", "")
    return {
        "arms": list(RECALL_ORACLE_CEILING_PAIRED_ARMS),
        "control_bytes": len(control.encode("utf-8")),
        "control_sha256": hashlib.sha256(control.encode("utf-8")).hexdigest(),
        "oracle_instruction_bytes": len(oracle.encode("utf-8")),
        "catalog_sha256": catalog.digest,
        "bundle_count": len(catalog.bundles),
        "item_count": sum(len(bundle.items) for bundle in catalog.bundles.values()),
        "task_ids": sorted(bundle.task_id for bundle in catalog.bundles.values()),
    }


def premutation_checkpoint_pair_metadata(texts: Mapping[str, str]) -> dict[str, Any]:
    """Record official-017's matched instruction and bounded checkpoint contract."""

    return {
        "arms": list(RECALL_PREMUTATION_CHECKPOINT_PAIRED_ARMS),
        "instruction_bytes_by_arm": {
            arm: len(texts.get(arm, "").encode("utf-8"))
            for arm in RECALL_PREMUTATION_CHECKPOINT_PAIRED_ARMS
        },
        "instruction_sha256_by_arm": {
            arm: hashlib.sha256(texts.get(arm, "").encode("utf-8")).hexdigest()
            for arm in RECALL_PREMUTATION_CHECKPOINT_PAIRED_ARMS
        },
        "checkpoint_k": 5,
        "query_limit_chars": CHECKPOINT_QUERY_LIMIT,
        "reason_limit_chars": CHECKPOINT_REASON_LIMIT,
        "max_injected_hits": CHECKPOINT_MAX_HITS,
        "hit_text_limit_chars": CHECKPOINT_HIT_TEXT_LIMIT,
    }


def prompt_time_pair_metadata(texts: Mapping[str, str]) -> dict[str, Any]:
    """Record the matched prompt identity for official-019."""

    return {
        "arms": list(RECALL_PROMPT_TIME_PAIRED_ARMS),
        "instruction_bytes_by_arm": {
            arm: len(texts.get(arm, "").encode("utf-8"))
            for arm in RECALL_PROMPT_TIME_PAIRED_ARMS
        },
        "instruction_sha256_by_arm": {
            arm: hashlib.sha256(texts.get(arm, "").encode("utf-8")).hexdigest()
            for arm in RECALL_PROMPT_TIME_PAIRED_ARMS
        },
        "hook_event": "UserPromptSubmit",
        "hook_matcher": None,
        "hook_max_hits": 3,
    }


def recall_preflight_request(arm: str, query: str) -> tuple[str, dict[str, Any]]:
    """Return the real read request that must pass before model spend."""

    if arm == RECALL_GRAPH_FULLTOOLS_DECISION_PROTOCOL_ARM:
        return "recall_search", {"query": query, "limit": 1}
    if arm == "recall_graph_rerank" or arm in RECALL_GRAPH_FULLTOOLS_ARMS:
        return (
            "recall_reasoning_query",
            {
                "query": query,
                "graph_expansion": "one_hop",
                "expand_retrieval": False,
            },
        )
    return "recall_search", {"query": query, "limit": 1}


def _graphiti_adapter():
    """Return the optional Graphiti adapter or explain why a Graphiti run cannot start."""

    if GraphitiAdapter is None or not GRAPHITI_CONFIG:
        raise RuntimeError(
            "Graphiti integration is unavailable; install or restore the complete "
            "adapters/graphiti package before selecting the graphiti arm"
        )
    return GraphitiAdapter


def memory_instructions(variant: str, arms: tuple[str, ...], *, neutral: bool = False) -> dict[str, str]:
    """The instruction each arm carries, keyed by arm. Arms with no memory surface carry "".

    Under a shared-protocol variant every memory arm gets that protocol verbatim plus its own capped
    appendix, and the fairness assertion below is meaningful. Under ``skill`` or ``oneliner`` the
    arms are deliberately NOT matched, because those variants exist to reproduce runs that were not
    matched, and the assertion is skipped with that stated in the artifact.
    """

    validate_quality_gate_pair(variant, arms)
    validate_decision_protocol_pair(variant, arms)
    validate_oracle_ceiling_pair(variant, arms)
    validate_premutation_checkpoint_pair(variant, arms)
    validate_prompt_time_pair(variant, arms)
    shared = variant in SHARED_PROTOCOL_VARIANTS
    texts = {arm: "" for arm in arms}
    if "recall" in texts:
        texts["recall"] = recall_instruction(variant, neutral=neutral)
    if "recall_rerank" in texts:
        # The SAME call, not a copy of the same words. `recall_rerank` varies retrieval and nothing
        # else, so its instruction must be byte-identical to `recall`'s; deriving both from one
        # function makes that true by construction, where a second appendix file could drift and
        # the drift would show up as a reranker effect.
        texts["recall_rerank"] = recall_instruction(variant, neutral=neutral)
    if "recall_graph_rerank" in texts:
        # Graph retrieval has a distinct MCP route. If this arm received the ordinary search
        # sentence, its graph would be ingested but never queried by the measured agent.
        texts["recall_graph_rerank"] = recall_graph_instruction(variant, neutral=neutral)
    if "recall_graph_fulltools" in texts:
        texts["recall_graph_fulltools"] = recall_graph_fulltools_instruction(
            variant, neutral=neutral
        )
    if RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM in texts:
        texts[RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM] = recall_graph_fulltools_instruction(
            "protocol"
        )
    if RECALL_GRAPH_FULLTOOLS_QUALITY_GATE_ARM in texts:
        texts[RECALL_GRAPH_FULLTOOLS_QUALITY_GATE_ARM] = (
            recall_graph_quality_gate_instruction()
        )
    if RECALL_GRAPH_FULLTOOLS_DECISION_PROTOCOL_ARM in texts:
        texts[RECALL_GRAPH_FULLTOOLS_DECISION_PROTOCOL_ARM] = (
            recall_decision_protocol_instruction()
        )
    if RECALL_GRAPH_FULLTOOLS_PROMPT_TIME_ARM in texts:
        texts[RECALL_GRAPH_FULLTOOLS_PROMPT_TIME_ARM] = recall_graph_fulltools_instruction(
            "protocol"
        )
    for checkpoint_arm in (
        RECALL_GRAPH_FULLTOOLS_CHECKPOINT_PLACEBO_ARM,
        RECALL_GRAPH_FULLTOOLS_CHECKPOINT_ARM,
    ):
        if checkpoint_arm in texts:
            texts[checkpoint_arm] = recall_graph_fulltools_instruction("protocol")
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
    if "cachly" in texts:
        texts["cachly"] = CachlyAdapter.shared_instruction(
            neutral=neutral, variant=variant if shared else "protocol"
        )
    if "graphiti" in texts:
        texts["graphiti"] = _graphiti_adapter().shared_instruction(
            neutral=neutral, variant=variant if shared else "protocol"
        )
    if "supermemory" in texts:
        texts["supermemory"] = SupermemoryAdapter.shared_instruction(
            neutral=neutral, variant=variant if shared else "protocol"
        )
    if "claude_mem" in texts:
        texts["claude_mem"] = ClaudeMemAdapter.shared_instruction(
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
    arm: str,
    task_bundle: dict[str, Path],
    staging: Path,
    texts: dict[str, str],
    oracle_catalog: MemoryBundleCatalog | None = None,
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
    if arm == "recall_rerank":
        return RecallRerankAdapter(
            staging, static, instruction=texts.get("recall_rerank") or None
        )
    if arm == "recall_graph_rerank":
        return RecallGraphRerankAdapter(
            staging, static, instruction=texts.get("recall_graph_rerank") or None
        )
    if arm == "recall_graph_fulltools":
        return RecallGraphFullToolsAdapter(staging, static, instruction=texts.get(arm) or None)
    if arm == RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM:
        return RecallGraphFullToolsProtocolAdapter(
            staging, static, instruction=texts.get(arm) or None
        )
    if arm == RECALL_GRAPH_FULLTOOLS_QUALITY_GATE_ARM:
        return RecallGraphFullToolsQualityGateAdapter(
            staging, static, instruction=texts.get(arm) or None
        )
    if arm == RECALL_GRAPH_FULLTOOLS_DECISION_PROTOCOL_ARM:
        return RecallGraphFullToolsDecisionProtocolAdapter(
            staging, static, instruction=texts.get(arm) or None
        )
    if arm == RECALL_GRAPH_FULLTOOLS_PROMPT_TIME_ARM:
        return RecallGraphFullToolsPromptTimeAdapter(
            staging, static, instruction=texts.get(arm) or None
        )
    if arm == RECALL_GRAPH_FULLTOOLS_CHECKPOINT_PLACEBO_ARM:
        return RecallGraphFullToolsCheckpointPlaceboAdapter(
            staging, static, instruction=texts.get(arm) or None
        )
    if arm == RECALL_GRAPH_FULLTOOLS_CHECKPOINT_ARM:
        return RecallGraphFullToolsCheckpointAdapter(
            staging, static, instruction=texts.get(arm) or None
        )
    if arm == "oracle_memory":
        if oracle_catalog is None:
            raise ValueError("oracle_memory requires a validated memory bundle catalog")
        return OracleMemoryAdapter(staging, static, oracle_catalog)
    if arm == "mempalace":
        return MemPalaceAdapter(staging, static, instruction=texts.get("mempalace") or None)
    if arm == "cachly":
        return CachlyAdapter(staging, static, instruction=texts.get("cachly") or None)
    if arm == "graphiti":
        return _graphiti_adapter()(staging, static, instruction=texts.get("graphiti") or None)
    if arm == "supermemory":
        return SupermemoryAdapter(staging, static, instruction=texts.get("supermemory") or None)
    if arm == "claude_mem":
        return ClaudeMemAdapter(staging, static, instruction=texts.get("claude_mem") or None)
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
    staging: Path,
    any_bundle: dict[str, Path],
    texts: dict[str, str],
    arms: tuple[str, ...],
    oracle_catalog: MemoryBundleCatalog | None = None,
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
        registry.register(
            adapter_for(arm, any_bundle, staging, texts, oracle_catalog)
        )
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


def checkpoint_metadata(record: Any, spec: ArmSpec) -> dict[str, Any]:
    """Recover the deny-once checkpoint receipt from the private participant record."""

    mode = spec.metadata.get("checkpoint_mode") if isinstance(spec.metadata, Mapping) else None
    if mode not in {"placebo", "treatment"}:
        return {}
    texts: list[str] = []
    calls = list(getattr(record, "tool_calls", ()))
    marker_call_index: int | None = None
    mutation_indices: list[int] = []
    for index, call in enumerate(calls):
        if isinstance(call, Mapping) and call.get("output") is not None:
            output = str(call.get("output"))
            texts.append(output)
            if marker_call_index is None and CHECKPOINT_MARKER in output:
                marker_call_index = index
        if not isinstance(call, Mapping) or call.get("is_error") is not False:
            continue
        args = call.get("args")
        if isinstance(args, Mapping) and is_mutation_candidate(str(call.get("name", "")), args):
            mutation_indices.append(index)
    denials = record.metadata.get("permission_denials", ())
    if isinstance(denials, (list, tuple)):
        texts.extend(str(item) for item in denials)
    marker_count = sum(text.count(CHECKPOINT_MARKER) for text in texts)
    parsed: dict[str, Any] | None = None
    for text in texts:
        if CHECKPOINT_MARKER not in text:
            continue
        try:
            parsed = parse_checkpoint_marker(text)
        except CheckpointError as error:  # malformed evidence is recorded and refused by admission
            parsed = {
                "mode": mode,
                "status": "error",
                "parse_error": type(error).__name__,
            }
        break
    diagnostic = {
        **(parsed or {}),
        "mode": (parsed or {}).get("mode", mode),
        "marker_count": marker_count,
        "triggered": marker_count > 0,
    }
    failed = int(record.metadata.get("failed_tool_calls", 0) or 0)
    unguarded = [
        index
        for index in mutation_indices
        if marker_call_index is None or index < marker_call_index
    ]
    return {
        "memory_checkpoint": diagnostic,
        "failed_tool_calls": max(0, failed - (1 if marker_count else 0)),
        "checkpoint_denials": 1 if marker_count else 0,
        "mutation_candidate_count": len(mutation_indices),
        "unguarded_mutation_count": len(unguarded),
    }


def prompt_time_hook_ledger(spec: ArmSpec) -> tuple[dict[str, Any], ...]:
    """Read the bounded prompt-time receipt written outside Claude's transcript."""

    raw_path = spec.metadata.get("prompt_time_trace") if isinstance(spec.metadata, Mapping) else None
    if not raw_path:
        return ()
    path = Path(str(raw_path))
    if not path.is_file():
        return ()
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            entries.append(value)
    return tuple(entries)


def cell_namespace(base_namespace: str, task_id: str, seed: int, arm: str) -> str:
    """Give Claude-Mem one live store per task and seed.

    Its lifecycle hooks persist benchmark sessions, so sharing one live worker lets an earlier
    cell inject its answer into a later cell's startup context. The imported corpus is cloned into
    each cell without repeating the vendor import.
    """

    if arm == "claude_mem":
        return f"{base_namespace}-{task_id}-s{seed}"
    return base_namespace


def sequence_namespace(base_namespace: str, chain_id: str, seed: int, arm: str) -> str:
    """Give every sequence chain and arm an isolated memory namespace.

    Chain identifiers are hashed before joining them to a namespace because the value is later
    passed to adapter path and tenant joins. The digest preserves stable identity without allowing
    a plan supplied identifier to become a path component.
    """

    chain_digest = hashlib.sha256(chain_id.encode("utf-8")).hexdigest()[:16]
    return f"{base_namespace}-seq-{chain_digest}-s{seed}-{arm}"


def session_capability_issuer() -> SessionCapabilityIssuer:
    """Build the controller-side issuer used for every participant invocation."""

    secret = os.environ.get("AMB_BROKER_SIGNING_SECRET", "").strip()
    if not secret:
        raise SystemExit(
            "AMB_BROKER_SIGNING_SECRET is unset; the controller cannot issue broker capabilities"
        )
    try:
        ttl_s = float(os.environ.get("AMB_BROKER_TOKEN_TTL_S", "3600"))
    except ValueError as error:
        raise SystemExit("AMB_BROKER_TOKEN_TTL_S must be a positive number") from error
    return SessionCapabilityIssuer(secret, ttl_s=ttl_s)


def issue_session_capabilities(
    issuer: SessionCapabilityIssuer,
    *,
    run_id: str,
    task_id: str,
    seed: int,
    arm: str,
    namespace: str,
    needs_memory: bool,
) -> tuple[str, str | None]:
    """Issue fresh model and optional memory grants for one exact session scope."""

    return issuer.issue(
        run_id=run_id,
        arm=arm,
        namespace=cell_namespace(namespace, task_id, seed, arm),
        memory=needs_memory,
    )


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
    parser.add_argument(
        "--seed-values",
        default="",
        help="exact comma-separated seed values to run; useful only for a controlled continuation",
    )
    parser.add_argument(
        "--continue-existing",
        action="store_true",
        help="continue an existing partial run using its challenge and runtime event log",
    )
    parser.add_argument(
        "--finalize-existing",
        action="store_true",
        help="rebuild signals and artifacts for an existing completed grid without running cells",
    )
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--namespace", default="bench-recall-pilot")
    parser.add_argument(
        "--sequence-plan",
        type=Path,
        help="run a bound longitudinal sequence plan instead of the ordinary grid",
    )
    parser.add_argument(
        "--heldout-manifest",
        type=Path,
        help="frozen held out manifest required by --sequence-plan",
    )
    parser.add_argument(
        "--memory-instruction",
        "--recall-instruction",
        dest="memory_instruction",
        choices=(
            "oneliner", "skill", "quality", "protocol", "draft",
            QUALITY_GATE_PAIRED_VARIANT, DECISION_PROTOCOL_PAIRED_VARIANT,
            ORACLE_CEILING_PAIRED_VARIANT, PREMUTATION_CHECKPOINT_PAIRED_VARIANT,
            PROMPT_TIME_PAIRED_VARIANT,
        ),
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
        "--emit-decisions",
        action="store_true",
        help="require each Claude session to finish with one schema-constrained decision object "
        "containing decision and confidence, and record it in runtime_decisions. This changes "
        "the prompt contract, so use it only in a separately preregistered run.",
    )
    parser.add_argument(
        "--emit-decision-stages",
        action="store_true",
        help="ask the runtime to label checkpoint decisions as pre_action, evidence, action, "
        "or final. Requires --emit-decisions and records only stages the runtime actually emits.",
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

    if args.seed_values:
        try:
            seed_values = [int(value.strip()) for value in args.seed_values.split(",") if value.strip()]
        except ValueError as error:
            raise SystemExit("--seed-values must be comma-separated integers") from error
        if not seed_values or len(seed_values) != len(set(seed_values)):
            raise SystemExit("--seed-values must contain at least one unique seed")
        if any(seed < 0 or seed >= args.seeds for seed in seed_values):
            raise SystemExit("--seed-values must be within 0..seeds-1")
    else:
        seed_values = list(range(args.seeds))
    if args.finalize_existing and args.continue_existing:
        raise SystemExit("--finalize-existing already implies --continue-existing")
    continuation = args.continue_existing or args.finalize_existing
    if continuation and args.dry_run:
        raise SystemExit("continuation modes cannot be combined with --dry-run")
    if args.emit_decision_stages and not args.emit_decisions:
        raise SystemExit("--emit-decision-stages requires --emit-decisions")

    # The preregistration guard applies to every invocation, including dry runs, because the
    # command should describe a committed protocol. Credentials are different: a dry run resolves
    # the grid and executes no model call, so it must remain usable before a participant has keys.
    # A real recall run with no DSN would have its treatment silently absent, which is exactly what
    # the admission gate exists to catch 216 sessions later.
    assert_preregistered(REPO)
    if not args.dry_run and not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set")
    run_arms = tuple(arm.strip() for arm in args.arms.split(",") if arm.strip())
    unknown = [arm for arm in run_arms if arm not in ARMS]
    if unknown:
        raise SystemExit(f"unknown arms {unknown}; choose from {ARMS}")
    if bool(args.sequence_plan) != bool(args.heldout_manifest):
        raise SystemExit("--sequence-plan and --heldout-manifest must be supplied together")
    sequence_plan = load_plan_file(args.sequence_plan) if args.sequence_plan else None
    heldout_manifest = (
        FrozenEvaluationManifest.load(args.heldout_manifest, root=REPO)
        if args.heldout_manifest
        else None
    )
    if sequence_plan is not None:
        if continuation:
            raise SystemExit("sequence runs do not support continuation modes yet")
        if set(sequence_plan.arms) != set(run_arms):
            raise SystemExit("sequence plan arms must exactly match --arms")
        assert heldout_manifest is not None
        try:
            validate_plan(sequence_plan, tasks_root=REPO / "tasks")
            validate_sequence_evaluation(
                sequence_plan,
                heldout_manifest,
                repo_root=REPO,
                tasks_root=REPO / "tasks",
            )
        except (OSError, TypeError, ValueError) as error:
            raise SystemExit(f"sequence preflight failed: {error}") from None
        plan_seed_values = sorted({chain.seed for chain in sequence_plan.chains})
        if args.seed_values and set(seed_values) != set(plan_seed_values):
            raise SystemExit("--seed-values must exactly match the sequence plan seeds")
        seed_values = plan_seed_values
        args.seeds = max(plan_seed_values) + 1
    try:
        validate_quality_gate_pair(args.memory_instruction, run_arms)
        validate_decision_protocol_pair(args.memory_instruction, run_arms)
        validate_oracle_ceiling_pair(
            args.memory_instruction, run_arms, condition=args.condition or None
        )
        validate_premutation_checkpoint_pair(
            args.memory_instruction, run_arms, condition=args.condition or None
        )
        validate_prompt_time_pair(args.memory_instruction, run_arms)
    except ValueError as error:
        raise SystemExit(str(error)) from None
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
    if RECALL_ARMS.intersection(run_arms) and not args.dry_run and not os.environ.get("RECALL_DSN"):
        raise SystemExit("RECALL_DSN is not set; the recall arm has no corpus")
    if "graphiti" in run_arms and not args.dry_run:
        missing = []
        if not os.environ.get(str(GRAPHITI_CONFIG["mcp_dir_env"])):
            missing.append(str(GRAPHITI_CONFIG["mcp_dir_env"]))
        graphiti_provider = os.environ.get(
            str(GRAPHITI_CONFIG["database_provider_env"]),
            str(GRAPHITI_CONFIG["database_provider_default"]),
        ).strip().lower()
        if (
            graphiti_provider == "neo4j"
            and not os.environ.get(str(GRAPHITI_CONFIG["neo4j_password_env"]))
        ):
            missing.append(str(GRAPHITI_CONFIG["neo4j_password_env"]))
        if not any(os.environ.get(str(name)) for name in GRAPHITI_CONFIG["llm_key_envs"]):
            missing.append(" or ".join(str(name) for name in GRAPHITI_CONFIG["llm_key_envs"]))
        if missing:
            raise SystemExit("Graphiti is not configured; set " + ", ".join(missing))
    if "supermemory" in run_arms and not args.dry_run:
        missing = [
            name
            for name in ("SUPERMEMORY_PLUGIN_DIR",)
            if not os.environ.get(name)
        ]
        if not (
            os.environ.get("SUPERMEMORY_CC_API_KEY")
            or os.environ.get("SUPERMEMORY_API_KEY")
        ):
            missing.append("SUPERMEMORY_CC_API_KEY or SUPERMEMORY_API_KEY")
        if missing:
            raise SystemExit(
                "Supermemory is not configured; set " + ", ".join(missing)
            )
    if "claude_mem" in run_arms and not args.dry_run:
        missing = [
            name
            for name in ("CLAUDE_MEM_PLUGIN_DIR",)
            if not os.environ.get(name)
        ]
        if not (
            os.environ.get("CLAUDE_MEM_OPENROUTER_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
        ):
            missing.append("CLAUDE_MEM_OPENROUTER_API_KEY or OPENROUTER_API_KEY")
        if missing:
            raise SystemExit(
                "Claude-Mem is not configured; set " + ", ".join(missing)
            )

    # A sequence plan is the task roster. The ordinary grid keeps its historical prefix and
    # explicit subset rules so enabling sequence mode cannot silently change an existing run.
    if sequence_plan is not None:
        if args.tasks:
            raise SystemExit("--tasks cannot be combined with --sequence-plan")
        discovered = {task.task_id: task for task in discover_tasks()}
        plan_task_ids = list(
            dict.fromkeys(
                session.task_id
                for chain in sequence_plan.chains
                for session in chain.sessions
            )
        )
        missing = [task_id for task_id in plan_task_ids if task_id not in discovered]
        if missing:
            raise SystemExit(f"sequence plan names unknown task(s) {missing}")
        tasks = [discovered[task_id] for task_id in plan_task_ids]
    else:
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

    try:
        validate_oracle_ceiling_pair(
            args.memory_instruction,
            run_arms,
            tasks=tasks,
            condition=args.condition or None,
        )
        validate_premutation_checkpoint_pair(
            args.memory_instruction,
            run_arms,
            tasks=tasks,
            condition=args.condition or None,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from None

    corpus_root = Path(args.corpus_root) if args.corpus_root else REPO / "corpus"
    oracle_catalog: MemoryBundleCatalog | None = None
    if args.memory_instruction == ORACLE_CEILING_PAIRED_VARIANT:
        if not (corpus_root / "manifest.json").is_file():
            raise SystemExit(f"{corpus_root} holds no manifest.json")
        try:
            oracle_catalog = load_oracle_ceiling_catalog(corpus_root, tasks)
        except (FileNotFoundError, OSError, TypeError, ValueError) as error:
            raise SystemExit(str(error)) from None

    texts = memory_instructions(
        args.memory_instruction, run_arms, neutral=args.neutral_protocol
    )

    if args.dry_run:
        # Placed BEFORE the run directory is created, so a dry run touches nothing at all.
        sessions = (
            sum(chain.length for chain in sequence_plan.chains) * len(run_arms)
            if sequence_plan is not None
            else len(tasks) * len(seed_values) * len(run_arms)
        )
        manifest = instructions.instruction_manifest(texts)
        print(f"[dry-run] run-id {args.run_id}, model {args.model}, seeds {seed_values}")
        print(f"[dry-run] arms   {list(run_arms)}")
        print(f"[dry-run] instruction variant {args.memory_instruction!r}, "
              f"neutral={args.neutral_protocol}")
        print(f"[dry-run] structured decisions {args.emit_decisions}")
        for arm in run_arms:
            print(f"[dry-run]   {arm:<10} instruction {manifest[arm]['bytes']:>5} bytes")
        if oracle_catalog is not None:
            print(f"[dry-run] oracle catalog {oracle_catalog.digest}")
        print(f"[dry-run] tasks  {len(tasks)}: {', '.join(task.task_id for task in tasks)}")
        if sequence_plan is not None:
            print(
                f"[dry-run] sequence plan {sequence_plan.plan_id}, "
                f"chains {len(sequence_plan.chains)}, "
                f"manifest {heldout_manifest.digest}"
            )
        print(f"[dry-run] work root {args.work_root or sandbox.default_work_root()}")
        print(f"[dry-run] would run {sessions} session(s); nothing written, nothing executed")
        return 0

    if not (corpus_root / "manifest.json").is_file():
        raise SystemExit(
            f"{corpus_root} holds no manifest.json. A condition corpus is built by "
            f"scripts/assemble_condition_corpus.py, which writes one; running against a feed "
            f"whose bytes nothing has hashed is how two arms end up ingesting different corpora."
        )

    run_dir = REPO / "results" / args.run_id
    existing_records = []
    if continuation:
        required = ("challenge.json", "execution-events.jsonl", "records.final.jsonl")
        missing = [name for name in required if not (run_dir / name).is_file()]
        if missing:
            raise SystemExit(f"cannot continue {run_dir}; missing {missing}")
        existing_records = read_jsonl(run_dir / "records.final.jsonl")
        if args.continue_existing:
            repair_cells = {(task.task_id, seed) for task in tasks for seed in seed_values}
            existing_records = [
                record for record in existing_records if record.cell not in repair_cells
            ]
    elif (run_dir / "records.jsonl").exists() or (run_dir / "records.final.jsonl").exists():
        raise SystemExit(f"{run_dir} already holds records; refusing to mix runs")
    work_root = Path(args.work_root) if args.work_root else sandbox.default_work_root() / args.run_id
    _refuse_a_dirty_work_root(work_root, args.run_id)
    staging = work_root / "staging"

    # A live result is accepted only when a trusted controller can bind it to a fresh challenge,
    # the measured runner and participant images, and the oracle tree used by the checker. The
    # private signing key is read once here and never enters a participant environment.
    runner_image_digest = os.environ.get("AMB_RUNNER_IMAGE_DIGEST", "").strip()
    participant_agent_digest = os.environ.get("AMB_PARTICIPANT_AGENT_DIGEST", "").strip()
    signing_key_file = os.environ.get("AMB_ADJUDICATOR_SIGNING_KEY_FILE", "").strip()
    ledger_file = os.environ.get("AMB_ADJUDICATOR_LEDGER_FILE", "").strip()
    print(
        "[diagnostic] adjudication env: "
        f"runner_len={len(runner_image_digest)} "
        f"runner_sha256={bool(re.fullmatch(r'sha256:[0-9a-f]{{64}}', runner_image_digest))} "
        f"agent_sha256={bool(re.fullmatch(r'sha256:[0-9a-f]{{64}}', participant_agent_digest))} "
        f"python={sys.executable}",
        flush=True,
    )
    if not runner_image_digest or not participant_agent_digest or not signing_key_file or not ledger_file:
        raise SystemExit(
            "trusted adjudication is required for live runs; set "
            "AMB_RUNNER_IMAGE_DIGEST, AMB_PARTICIPANT_AGENT_DIGEST, and "
            "AMB_ADJUDICATOR_SIGNING_KEY_FILE, and AMB_ADJUDICATOR_LEDGER_FILE"
        )
    if continuation:
        try:
            challenge = Challenge.from_mapping(
                json.loads((run_dir / "challenge.json").read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise SystemExit(f"existing challenge is unreadable: {run_dir / 'challenge.json'}") from error
        if challenge.run_id != args.run_id:
            raise SystemExit("existing challenge belongs to a different run id")
    else:
        challenge = issue_challenge(
            run_dir,
            run_id=args.run_id,
            runner_image_digest=runner_image_digest,
            participant_agent_digest=participant_agent_digest,
            oracle_version=f"sha256:{tree_digest(REPO / 'oracles')}",
        )
    event_log = RuntimeEventLog(run_dir / "execution-events.jsonl", challenge)
    if not continuation:
        event_log.append(
            "run_started",
            {"task_count": len(tasks), "seed_count": args.seeds, "arms": list(run_arms)},
        )

    bundles = {
        task.task_id: build_bundles(task, run_dir / "cfg" / task.task_id, texts)
        for task in tasks
    }
    registry = build_registry(
        staging,
        bundles[tasks[0].task_id],
        texts,
        run_arms,
        oracle_catalog,
    )

    # Ingestion, for the arms whose store this runner owns. recall's tenant is indexed out of band
    # against the frozen corpus manifest; fs_grep's render is local, cheap and reproducible here.
    ingest_reports: list[IngestReport] = []
    corpus = CorpusManifest.load(corpus_root) if (
        RECALL_ARMS.intersection(run_arms) or any(arm in run_arms for arm in SELF_INGESTING_ARMS)
    ) else None
    self_ingesting = [arm for arm in SELF_INGESTING_ARMS if arm in run_arms]
    if not args.finalize_existing and self_ingesting:
        assert corpus is not None
        for arm in self_ingesting:
            print(f"[ingest] {arm} from {corpus_root}", flush=True)
            report = registry.get(arm).ingest(corpus, args.namespace)
            print(
                f"[ingest] {arm}: {report.items_stored} item(s) from "
                f"{report.sessions_offered} session(s)",
                flush=True,
            )
            ingest_reports.append(report)
    if not args.finalize_existing and "claude_mem" in self_ingesting:
        claude_mem_namespaces = tuple(
            cell_namespace(args.namespace, task.task_id, seed, "claude_mem")
            for task in tasks
            for seed in range(args.seeds)
        )
        if sequence_plan is not None:
            claude_mem_namespaces = tuple(
                {
                    *claude_mem_namespaces,
                    *(
                        sequence_namespace(
                            args.namespace, chain.chain_id, chain.seed, "claude_mem"
                        )
                        for chain in sequence_plan.chains
                    ),
                }
            )
        registry.get("claude_mem").isolate_cell_namespaces(
            args.namespace, claude_mem_namespaces
        )
    recall_arms = list(dict.fromkeys(arm for arm in run_arms if arm in RECALL_ARMS))
    if not args.finalize_existing and recall_arms:
        # Recall is indexed out of band, but a run still has to prove here that its tenant serves
        # the active generation built from THIS frozen manifest. Previously pilot.py skipped this
        # check because the abstention wrapper happened to perform it, leaving direct pilot runs
        # able to spend against a missing or stale tenant. Each selected adapter gets its ingest
        # hook too: paired treatments may materialize controller-side state in addition to this
        # shared remote-generation verification.
        assert corpus is not None
        for recall_arm in recall_arms:
            print(f"[verify] recall generation for {args.namespace} ({recall_arm})", flush=True)
            report = registry.get(recall_arm).ingest(corpus, args.namespace)
            ingest_reports.append(report)
            print(
                f"[verify] recall {recall_arm}: "
                f"{report.notes[-1] if report.notes else 'generation verified'}",
                flush=True,
            )
        # The MCP preflight below is intentionally issued from the first selected recall arm,
        # which is the reference surface for paired runs. Do not let the loop variable above
        # silently select the last treatment arm.
        recall_arm = recall_arms[0]

    provider_policy = None
    if not args.dry_run:
        try:
            provider_policy = load_provider_policy(os.environ.get("AMB_DATA_POLICY_FILE"))
        except ValueError as error:
            raise SystemExit(str(error)) from error
    if not os.environ.get("AMB_BROKER_SIGNING_SECRET"):
        raise SystemExit(
            "AMB_BROKER_SIGNING_SECRET is not set; the controller cannot issue broker capabilities"
        )
    capability_issuer = session_capability_issuer()

    # One ArmSpec per (task, arm), built by that arm's own adapter. This is the measured path, and
    # until 2026-08-28 it was inline code here instead, so `adapters/` was reviewable and not run.
    specs: dict[tuple[str, str], ArmSpec] = {}
    cell_specs: dict[tuple[str, int, str], ArmSpec] = {}
    for task in tasks:
        for arm in run_arms:
            adapter = adapter_for(
                arm,
                bundles[task.task_id],
                staging,
                texts,
                oracle_catalog,
            )
            namespace = cell_namespace(args.namespace, task.task_id, 0, arm)
            specs[(task.task_id, arm)] = adapter.build_for_task(
                run_dir / "cfg" / task.task_id / arm,
                namespace,
                task.task_id,
                task.prompt,
            )
            # Claude Code mutates CLAUDE_CONFIG_DIR while a session runs. Seeds of one task can
            # execute concurrently, so sharing the task/arm directory lets their settings,
            # session state, or hook ledger race and can produce silent zero-token completions.
            # Seed zero keeps the historical path; every additional seed gets its own identical
            # config copy. Claude-Mem also gets a task-seed worker namespace with the same imported
            # snapshot, preventing live lifecycle observations from crossing cell boundaries.
            cell_specs[(task.task_id, 0, arm)] = specs[(task.task_id, arm)]
            for seed in range(1, args.seeds):
                namespace = cell_namespace(args.namespace, task.task_id, seed, arm)
                cell_specs[(task.task_id, seed, arm)] = adapter.build_for_task(
                    run_dir / "cfg" / task.task_id / f"s{seed}" / arm,
                    namespace,
                    task.task_id,
                    task.prompt,
                )

    sequence_specs: dict[tuple[str, str, int, str], ArmSpec] = {}
    if sequence_plan is not None:
        sequence_tasks = {task.task_id: task for task in tasks}
        for chain in sequence_plan.chains:
            chain_digest = hashlib.sha256(chain.chain_id.encode("utf-8")).hexdigest()[:16]
            for session in chain.sessions:
                task = sequence_tasks[session.task_id]
                for arm in run_arms:
                    adapter = adapter_for(
                        arm,
                        bundles[task.task_id],
                        staging,
                        texts,
                        oracle_catalog,
                    )
                    namespace = sequence_namespace(
                        args.namespace, chain.chain_id, chain.seed, arm
                    )
                    sequence_specs[(chain.chain_id, task.task_id, chain.seed, arm)] = (
                        adapter.build_for_task(
                            run_dir / "cfg" / "sequence" / chain_digest / task.task_id / arm,
                            namespace,
                            task.task_id,
                            task.prompt,
                        )
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

    recall_preflight: dict[str, Any] = {"status": "not_required"}
    if recall_arm is not None:
        # This is a real MCP tools/call, not only a process handshake. An empty result is valid,
        # because an empty corpus response is a successful retrieval; a transport or server error
        # is not. The result is written into environment.json before setup validation refuses a
        # broken run, so the refusal remains auditable.
        spec = specs[(tasks[0].task_id, recall_arm)]
        required = [name.removeprefix(RECALL_PREFIX) for name in spec.extra_allowed_tools]
        probe_tool, probe_arguments = recall_preflight_request(
            recall_arm, tasks[0].prompt
        )
        try:
            _, memory_capability = issue_session_capabilities(
                capability_issuer,
                run_id=args.run_id,
                task_id=tasks[0].task_id,
                seed=0,
                arm=recall_arm,
                namespace=args.namespace,
                needs_memory=True,
            )
            # The controller and participant run in different network namespaces on the host. The
            # participant-facing broker URL is a Docker DNS name; the controller preflight uses
            # the explicit host-published endpoint when supplied.
            tools = probe_jsonrpc_endpoint(
                os.environ.get(
                    "AMB_CONTROLLER_MEMORY_BROKER_URL",
                    os.environ.get("AMB_MEMORY_BROKER_URL", ""),
                ),
                memory_capability or "",
                tuple(required),
                probe_tool=probe_tool,
                probe_arguments=probe_arguments,
            )
            recall_preflight = {
                "status": "passed",
                "server": RECALL_CONFIG["server_name"],
                "required_tools": required,
                "tools_observed": tools,
                "probe": f"tools/call {probe_tool} succeeded",
            }
            print(f"[preflight] recall MCP and search up: {len(tools)} tool(s)", flush=True)
        except Exception as exc:  # noqa: BLE001, the setup gate records the concrete refusal
            recall_preflight = {
                "status": "failed",
                "server": RECALL_CONFIG["server_name"],
                "required_tools": required,
                "error": str(exc)[-2000:],
            }
            print(
                f"[preflight] recall FAILED: {recall_preflight['error']}",
                file=sys.stderr,
                flush=True,
            )

    claude_mem_preflight: dict[str, Any] = {"status": "not_required"}
    if "claude_mem" in run_arms:
        # Claude-Mem is self-hosted and its MCP server reaches the per-cell worker over HTTP.
        # Start the exact first cell worker for this probe, then stop it before the measured
        # session. This proves the complete MCP path without turning the probe into a model call.
        spec = specs[(tasks[0].task_id, "claude_mem")]
        required = [name.removeprefix(CLAUDE_MEM_PREFIX) for name in spec.extra_allowed_tools]
        try:
            _, memory_capability = issue_session_capabilities(
                capability_issuer,
                run_id=args.run_id,
                task_id=tasks[0].task_id,
                seed=0,
                arm="claude_mem",
                namespace=args.namespace,
                needs_memory=True,
            )
            tools = probe_jsonrpc_endpoint(
                os.environ.get("AMB_MEMORY_BROKER_URL", ""),
                memory_capability or "",
                tuple(required),
                probe_tool="search",
                probe_arguments={"query": tasks[0].prompt},
            )
            claude_mem_preflight = {
                "status": "passed",
                "server": CLAUDE_MEM_CONFIG["server_name"],
                "required_tools": required,
                "tools_observed": tools,
                "search": "tools/call search succeeded",
            }
            print(f"[preflight] claude_mem MCP and search up: {len(tools)} tool(s)", flush=True)
        except Exception as exc:  # noqa: BLE001, setup validation records the refusal
            claude_mem_preflight = {
                "status": "failed",
                "server": CLAUDE_MEM_CONFIG["server_name"],
                "required_tools": required,
                "error": str(exc)[-2000:],
            }
            print(
                f"[preflight] claude_mem FAILED: {claude_mem_preflight['error']}",
                file=sys.stderr,
                flush=True,
            )

    graphiti_preflight: dict[str, Any] = {"status": "not_required"}
    if "graphiti" in run_arms:
        spec = specs[(tasks[0].task_id, "graphiti")]
        required = [name.removeprefix(GRAPHITI_PREFIX) for name in spec.extra_allowed_tools]
        try:
            _, memory_capability = issue_session_capabilities(
                capability_issuer,
                run_id=args.run_id,
                task_id=tasks[0].task_id,
                seed=0,
                arm="graphiti",
                namespace=args.namespace,
                needs_memory=True,
            )
            tools = probe_jsonrpc_endpoint(
                os.environ.get("AMB_MEMORY_BROKER_URL", ""),
                memory_capability or "",
                tuple(required),
                probe_tool="get_status",
                probe_arguments={},
            )
            graphiti_preflight = {
                "status": "passed",
                "server": GRAPHITI_CONFIG["server_name"],
                "required_tools": required,
                "tools_observed": tools,
                "search": "tools/call get_status succeeded",
            }
            print(f"[preflight] graphiti MCP and status up: {len(tools)} tool(s)", flush=True)
        except Exception as exc:  # noqa: BLE001, setup validation records the refusal
            graphiti_preflight = {
                "status": "failed",
                "server": GRAPHITI_CONFIG["server_name"],
                "required_tools": required,
                "error": str(exc)[-2000:],
            }
            print(
                f"[preflight] graphiti FAILED: {graphiti_preflight['error']}",
                file=sys.stderr,
                flush=True,
            )

    if args.memory_instruction == QUALITY_GATE_PAIRED_VARIANT:
        shared_tool_prefix_groups = (RECALL_GRAPH_FULLTOOLS_PAIRED_ARMS,)
    elif args.memory_instruction == DECISION_PROTOCOL_PAIRED_VARIANT:
        shared_tool_prefix_groups = (RECALL_GRAPH_FULLTOOLS_DECISION_PAIRED_ARMS,)
    elif args.memory_instruction == PREMUTATION_CHECKPOINT_PAIRED_VARIANT:
        shared_tool_prefix_groups = (RECALL_PREMUTATION_CHECKPOINT_PAIRED_ARMS,)
    elif args.memory_instruction == PROMPT_TIME_PAIRED_VARIANT:
        shared_tool_prefix_groups = (RECALL_PROMPT_TIME_PAIRED_ARMS,)
    else:
        shared_tool_prefix_groups = ()
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
        },
        shared_prefix_groups=shared_tool_prefix_groups,
    )
    signal_snapshot = admission_signal_snapshot(signals)
    signal_digest = json_digest(signal_snapshot)
    if not continuation:
        event_log.append(
            "admission_signals",
            {"signals_sha256": signal_digest, "arms": sorted(signal_snapshot)},
        )

    (run_dir / "environment.json").write_text(
        json.dumps(
            {
                "run_id": args.run_id,
                "model": args.model,
                "base_url": args.base_url,
                "execution_mode": "rootless-docker",
                "runtime_name": "docker",
                "participant_image_digest": default_participant_policy().effective_image_digest,
                "checker_image_digest": os.environ.get("AMB_CHECKER_IMAGE_DIGEST", ""),
                "isolation_policy_digest": default_participant_policy().digest,
                "network_policy_digest": default_participant_policy().network_policy_digest,
                "participant_isolation_verified": bool(
                    os.environ.get("AMB_PARTICIPANT_IMAGE_DIGEST")
                    and os.environ.get("AMB_CHECKER_IMAGE_DIGEST")
                    and os.environ.get("AMB_NETWORK_POLICY_DIGEST")
                ),
                "oracle_visible_to_participant": False,
                "arms": list(run_arms),
                "sequence_evaluation": (
                    {
                        "plan_id": sequence_plan.plan_id,
                        "plan_digest": sequence_plan.digest,
                        "manifest_id": heldout_manifest.data["manifest_id"],
                        "manifest_digest": heldout_manifest.digest,
                        "chains": len(sequence_plan.chains),
                        "chain_lengths": sorted({chain.length for chain in sequence_plan.chains}),
                    }
                    if sequence_plan is not None and heldout_manifest is not None
                    else None
                ),
                "memory_instruction": args.memory_instruction,
                "condition": args.condition,
                "neutral_protocol": args.neutral_protocol,
                "decision_output": {
                    "enabled": args.emit_decisions,
                    "staged": args.emit_decision_stages,
                    "schema": (
                        STAGED_DECISION_OUTPUT_SCHEMA
                        if args.emit_decision_stages
                        else DECISION_OUTPUT_SCHEMA
                    ) if args.emit_decisions else None,
                    "instruction_sha256": (
                        hashlib.sha256(
                            (
                                DECISION_OUTPUT_INSTRUCTION
                                + (f"\n\n{DECISION_STAGE_INSTRUCTION}" if args.emit_decision_stages else "")
                            ).encode("utf-8")
                        ).hexdigest()
                        if args.emit_decisions
                        else None
                    ),
                    "confidence_semantics": (
                        "probability that the requested task was completed correctly"
                        if args.emit_decisions
                        else None
                    ),
                },
                # The fairness disclosure, published beside the success rates. Under `skill` the
                # recall arm carries thousands of bytes more than any other; under `protocol` the
                # gap is each product's capped result-schema appendix and nothing else.
                "instruction_manifest": instructions.instruction_manifest(texts),
                "instruction_excess_bytes": instructions.excess_over_protocol(
                    texts, neutral=args.neutral_protocol
                ),
                "instruction_arms_matched": args.memory_instruction in {
                    "protocol", PREMUTATION_CHECKPOINT_PAIRED_VARIANT,
                    PROMPT_TIME_PAIRED_VARIANT,
                },
                "quality_gate_pair": (
                    quality_gate_pair_metadata(texts)
                    if args.memory_instruction == QUALITY_GATE_PAIRED_VARIANT
                    else None
                ),
                "decision_protocol_pair": (
                    decision_protocol_pair_metadata(texts)
                    if args.memory_instruction == DECISION_PROTOCOL_PAIRED_VARIANT
                    else None
                ),
                "oracle_ceiling_pair": (
                    oracle_ceiling_pair_metadata(texts, oracle_catalog)
                    if args.memory_instruction == ORACLE_CEILING_PAIRED_VARIANT
                    and oracle_catalog is not None
                    else None
                ),
                "premutation_checkpoint_pair": (
                    premutation_checkpoint_pair_metadata(texts)
                    if args.memory_instruction == PREMUTATION_CHECKPOINT_PAIRED_VARIANT
                    else None
                ),
                "prompt_time_pair": (
                    prompt_time_pair_metadata(texts)
                    if args.memory_instruction == PROMPT_TIME_PAIRED_VARIANT
                    else None
                ),
                "shared_tool_prefix_groups": [
                    list(group) for group in shared_tool_prefix_groups
                ],
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
                "cell_namespace_policy": {
                    "claude_mem": "one cloned post-import worker namespace per task-seed cell",
                    "import_reuse": "one vendor import before cloning; no per-cell re-ingestion",
                },
                "work_root": "external-disposable-storage",
                "sandbox_inside_repo": False,
                "adapters": {
                    arm: registry.get(arm).describe()
                    for arm in run_arms
                    if arm in registry.names()
                },
                "ingest": [report.to_dict() for report in ingest_reports],
                "recall_preflight": recall_preflight,
                "claude_mem_preflight": claude_mem_preflight,
                "graphiti_preflight": graphiti_preflight,
                "provider_data_policy": provider_policy_metadata(provider_policy),
                "admission_signals": signal_snapshot,
                "adjudication": {
                    "schema": "amb-adjudication-receipt-v1",
                    "required": True,
                    "challenge_version": challenge.version,
                    "challenge_id": challenge.challenge_id,
                    "nonce": challenge.nonce,
                    "runner_image_digest": challenge.runner_image_digest,
                    "participant_agent_digest": challenge.participant_agent_digest,
                    "oracle_version": challenge.oracle_version,
                    "event_log": "execution-events.jsonl",
                    "receipt": "adjudication.receipt.json",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # Refuse a misconfigured run HERE, before a single session is spent.
    #
    # This is the cheapest point there is: ingest is done (~20 min on the official corpus) and
    # the sessions are not (~11 h, and the whole model bill). Both of this project's expensive
    # failures were plainly visible in the dict written just above, and nobody compared it to an
    # expectation. `official-002` published `instruction_excess_bytes` showing recall at 1,958
    # bytes against mempalace's 853 for the whole of its life and its headline finding had to be
    # withdrawn; the haystackless corpora published `sessions_offered: 207`. Recording a number
    # is not checking it, and provenance without assertion reads exactly like provenance with it.
    #
    # The instruction checks are INVARIANTS and are always enforced: a roster whose arms do not
    # share one protocol byte for byte is not measuring what it claims, whatever the run is for.
    #
    # The corpus floor is an EXPECTATION and is enforced only when supplied, because small
    # corpora are legitimate here: `diagnostic-010` ran 125 sessions deliberately.
    # `launch_official.sh` exports AMB_CORPUS_FLOOR because an official run always uses the
    # haystack; a pilot leaves it unset and that check reports SKIP rather than passing.
    setup_env = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
    setup_checks = validate_setup(
        setup_env, corpus_floor=int(os.environ.get("AMB_CORPUS_FLOOR", "0"))
    )
    for check in setup_checks:
        if check.ok is not True:
            print(f"[setup] {check.mark} {check.name}: {check.detail}", flush=True)
    if any(check.ok is False for check in setup_checks):
        print(
            "\n[setup] REFUSING to run sessions: this run is not configured to measure what it "
            "claims. Nothing has been spent beyond ingest. Fix the setup, or say why the check is "
            "wrong and change the check; do not route around it.",
            file=sys.stderr,
            flush=True,
        )
        return 2

    by_id = {task.task_id: task for task in tasks}

    env = {
        "ANTHROPIC_BASE_URL": args.base_url,
        "ANTHROPIC_AUTH_TOKEN": "",
        "ANTHROPIC_API_KEY": "",
    }

    def spec_for_row(row: Mapping[str, Any], arm: str) -> ArmSpec:
        sequence = row.get("sequence")
        if sequence is not None:
            if not isinstance(sequence, Mapping):
                raise TypeError("row sequence metadata must be a mapping")
            chain_id = str(sequence.get("chain_id", ""))
            key = (chain_id, str(row["task_id"]), int(row.get("seed", 0)), arm)
            try:
                return sequence_specs[key]
            except KeyError as error:
                raise ValueError(f"no sequence adapter spec for {key!r}") from error
        return cell_specs[(str(row["task_id"]), int(row.get("seed", 0)), arm)]

    def config_for(row: Mapping[str, Any], arm: str, cwd: Path) -> ClaudeExecConfig:
        """Everything the harness controls is here; everything the product controls is in the spec.

        The split is the neutrality claim made mechanical: model, timeout, tool allow/deny list,
        permission mode and sandbox are identical for every arm and set here, and the only per-arm
        values are the four the adapter returned.
        """

        spec = spec_for_row(row, arm)
        return ClaudeExecConfig(
            # The participant image supplies /usr/local/bin/claude. The controller only needs a
            # local executable to satisfy command construction; isolation.py replaces argv[0]
            # with the image path before starting the container.
            executable="/bin/true",
            model=args.model,
            cwd=cwd,
            timeout_s=args.timeout,
            env={**env, **spec.env},
            bare=spec.bare,
            config_dir=spec.config_dir,
            mcp_config=spec.mcp_config,
            strict_mcp_config=bool(spec.mcp_config),
            allowed_tools=BASE_TOOLS + spec.extra_allowed_tools,
            disallowed_tools=DENIED_TOOLS,
            extra_args=spec.extra_args,
            append_system_prompt_file=spec.append_system_prompt_file,
            permission_mode="acceptEdits",
            memory_tool_prefix=spec.memory_tool_prefix or "mcp__never__",
            memory_event_tools=spec.metadata.get("memory_event_tools", {}),
            stream_dir=work_root / "private-streams",
            json_schema=(
                STAGED_DECISION_OUTPUT_SCHEMA
                if args.emit_decision_stages
                else DECISION_OUTPUT_SCHEMA
            ) if args.emit_decisions else None,
        )

    # Raw records stay outside the repository. The result directory is a publication boundary.
    records_path = work_root / "records.private.jsonl"
    records_path.parent.mkdir(parents=True, exist_ok=True)
    # `--namespace` is a CLI argument and this path is handed to the fs_grep arm as its
    # store. Validated here for the same reason the adapter validates its own join.
    fs_grep_memory = (
        namespace_path(staging, args.namespace, "memory") if "fs_grep" in run_arms
        else None
    )

    async def runner(row, arm):
        task_id, seed = str(row["task_id"]), int(row["seed"])
        sequence = row.get("sequence")
        if sequence is not None:
            if not isinstance(sequence, Mapping):
                raise TypeError("row sequence metadata must be a mapping")
            chain_id = str(sequence["chain_id"])
            chain_digest = hashlib.sha256(chain_id.encode("utf-8")).hexdigest()[:16]
            session_namespace = sequence_namespace(args.namespace, chain_id, seed, arm)
            workdir = work_root / "work" / "sequence" / chain_digest / task_id / f"s{seed}" / arm
        else:
            session_namespace = cell_namespace(args.namespace, task_id, seed, arm)
            workdir = work_root / "work" / task_id / f"s{seed}" / arm
        overlay = (
            namespace_path(staging, session_namespace, "memory")
            if arm == "fs_grep" and sequence is not None
            else fs_grep_memory if arm == "fs_grep" else None
        )
        digest = sandbox.restore(task_id, workdir, overlay=overlay)
        session_config = config_for(row, arm, workdir)
        model_capability, memory_capability = issue_session_capabilities(
            capability_issuer,
            run_id=args.run_id,
            task_id=task_id,
            seed=seed,
            arm=arm,
            namespace=session_namespace,
            needs_memory=session_config.mcp_config is not None,
        )
        silent_retries = 0
        max_silent_retries = min(
            5, max(0, int(os.environ.get("AMB_SILENT_COMPLETION_RETRIES", "1")))
        )
        while True:
            event_log.append(
                "participant_started",
                {"task_id": task_id, "arm": arm, "seed": seed, "attempt": silent_retries},
            )
            record = await asyncio.to_thread(
                run_isolated_claude_case,
                row,
                arm,
                session_config,
                workspace_digest=digest,
                model_capability=model_capability,
                memory_capability=memory_capability,
            )
            silent = not record.response and not record.tool_calls and record.error is None
            if not silent or silent_retries >= max_silent_retries:
                break
            silent_retries += 1
            await asyncio.sleep(2.0 * silent_retries)
        event_log.append(
            "participant_completed",
            {
                "task_id": task_id,
                "arm": arm,
                "seed": seed,
                "attempt": silent_retries,
                "final": True,
                "success": record.success,
                "error": bool(record.error),
                "participant_isolation_verified": record.metadata.get(
                    "participant_isolation_verified"
                ),
                "oracle_visible_to_participant": record.metadata.get(
                    "oracle_visible_to_participant"
                ),
                "workspace_output_digest": record.metadata.get("workspace_output_digest"),
            },
        )
        if silent_retries:
            record = replace(
                record,
                metadata={
                    **record.metadata,
                    "silent_completion_retries": silent_retries,
                },
            )
        ok, verdict = run_isolated_checker(
            task_id,
            by_id[task_id].oracle_dir.parent,
            workdir,
        )
        event_log.append(
            "checker_completed",
            {
                "task_id": task_id,
                "arm": arm,
                "seed": seed,
                "ok": bool(ok),
                "verdict_sha256": hashlib.sha256(verdict.encode("utf-8")).hexdigest(),
                "checker_network": "none",
                "oracle_read_only": True,
            },
        )
        spec = spec_for_row(row, arm)
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
        checkpoint_extra = checkpoint_metadata(record, spec)
        hook_ledger = record.hook_ledger
        prompt_time_extra: dict[str, Any] = {}
        if arm == RECALL_GRAPH_FULLTOOLS_PROMPT_TIME_ARM:
            hook_ledger = prompt_time_hook_ledger(spec)
            prompt_time_extra = {
                "prompt_time_hook": dict(hook_ledger[-1]) if hook_ledger else None,
                "prompt_time_snapshot_manifest": spec.metadata.get(
                    "prompt_time_snapshot_manifest"
                ),
            }

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
            **checkpoint_extra,
            **prompt_time_extra,
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
            config_dir_digest=spec.config_dir_digest,
            hook_ledger=hook_ledger if arm == RECALL_GRAPH_FULLTOOLS_PROMPT_TIME_ARM else (
                registry.get(arm).read_hook_ledger(
                    record.metadata.get("session_id"), spec.config_dir
                )
                if arm in ("supermemory", "claude_mem")
                and spec.config_dir is not None
                else record.hook_ledger
            ),
            metadata={**record.metadata, **extra},
        )
        # Fsynced per session: a run that dies keeps every finished cell.
        with records_path.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(final.to_dict()) + "\n")
            sink.flush()
            os.fsync(sink.fileno())
        return final

    if args.finalize_existing:
        records = existing_records
        wall_min = 0.0
        print(f"[finalize] reusing {len(records)} existing records; no sessions executed", flush=True)
    elif sequence_plan is not None:
        assert heldout_manifest is not None
        print(
            f"[sequence] {len(sequence_plan.chains)} chains, "
            f"{sum(chain.length for chain in sequence_plan.chains)} positions, "
            f"{len(run_arms)} arms",
            flush=True,
        )
        started = time.monotonic()
        records = await run_sequences(
            sequence_plan,
            runner,
            heldout_manifest=heldout_manifest,
            chain_concurrency=block_concurrency(),
        )
        wall_min = (time.monotonic() - started) / 60
    else:
        rows = [
            {
                "task_id": task.task_id,
                "seed": seed,
                "user_input": (
                    with_decision_output_instruction(
                        task.prompt, staged=args.emit_decision_stages
                    )
                    if args.emit_decisions
                    else task.prompt
                ),
            }
            for task in tasks
            for seed in seed_values
        ]
        print(
            f"[pilot] {len(rows)} cells x {len(run_arms)} arms = {len(rows) * len(run_arms)} sessions, "
            f"model {args.model}",
            flush=True,
        )
        started = time.monotonic()
        records = await run_grid(rows, run_arms, runner, block_concurrency=block_concurrency())
        if existing_records:
            records = [*existing_records, *records]
        wall_min = (time.monotonic() - started) / 60

    write_public_jsonl(run_dir / "records.final.jsonl", records)
    report = admit_cells(records, signals, required_arms=run_arms)
    admission_summary = report.summary()
    admission_summary["runtime_signals_sha256"] = signal_digest
    (run_dir / "admission.json").write_text(
        json.dumps(admission_summary, indent=2), encoding="utf-8"
    )
    pricing = pricing_from_args(args, model=args.model, source="https://openrouter.ai/api/v1/models")
    costs = summarize(records, ingest_reports, pricing=pricing, model=args.model)
    admitted_cells = {record.cell: True for record in report.admitted}
    costs["efficiency"] = efficiency(records, admitted_cells=admitted_cells)
    (run_dir / "costs.json").write_text(json.dumps(costs, indent=2), encoding="utf-8")

    # Raw streams are produced in disposable private storage while sessions run. Promote the
    # completed evidence into the result boundary before adjudication hashes the run; otherwise
    # a fully executed grid can be mistaken for an incomplete artifact set.
    private_streams = work_root / "private-streams"
    if not private_streams.is_dir() and not continuation:
        raise SystemExit(f"private stream directory is missing: {private_streams}")
    if private_streams.is_dir():
        shutil.copytree(private_streams, run_dir / "streams", dirs_exist_ok=True)

    adjudicate_run(
        run_dir,
        signer=load_private_signer(
            signing_key_file,
            key_id=os.environ.get("AMB_ADJUDICATOR_KEY_ID", "adjudicator"),
        ),
        ledger_path=ledger_file,
    )

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
    searches = [r for r in report.admitted if r.arm in RECALL_ARMS]
    if searches:
        for arm in sorted({r.arm for r in searches}):
            arm_searches = [r for r in searches if r.arm == arm]
            search_rate = sum(1 for r in arm_searches if r.memory_call_count > 0) / len(arm_searches)
            print(f"  {arm} memory search rate: {search_rate:.3f}")
    print(f"  estimated spend: ${costs.get('estimated_usd')} ({costs['total_tokens']} tokens)")
    print(f"  adjudication receipt: {run_dir / 'adjudication.receipt.json'}")
    print(f"  artifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
