"""Build the one-shot Code 4 plus Context 4 hybrid-suffix evidence artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from harness.adapters.base import CorpusManifest
from harness.memory_prompt import sha256_text
from harness.tasks import discover_tasks
from scripts.code_context4_replacement_experiment import (
    DEFAULT_CONTROL_MODEL,
    DEFAULT_TREATMENT_MODEL,
    FROZEN_MAX_TOKENS_PER_MODEL,
    VoyageContext4,
)
from scripts.code_embedding_replacement_experiment import (
    DEFAULT_CANDIDATE_K,
    RRF_K,
    first_gold_rank,
    fused_ranking,
    rank_scores,
)
from scripts.retrieval_probe import (
    BM25,
    WINDOW_STRIDE,
    WINDOW_WORDS,
    Voyage,
    estimate_tokens,
    load_windows,
)

EXPERIMENT = "097-code4-context4-hybrid-suffix-evidence"
SOURCE_EVIDENCE_PATH = Path("results/retrieval/096-code4-context4-suffix-evidence.json")
SOURCE_EVIDENCE_SHA256 = "12549dbc27e37ab2d6a2d9a40ad0ce0953bd3cda5e0392fdf9d730aac71aa509"
CONTROL_ARM = "code4_12_replay"
TREATMENT_ARM = "code4_context4_hybrid_12_replay"
PROTECTED_PREFIX_K = 10
EVIDENCE_K = 12


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_source_evidence(root: Path, manifest_sha256: str) -> None:
    path = root / SOURCE_EVIDENCE_PATH
    if _sha256_file(path) != SOURCE_EVIDENCE_SHA256:
        raise ValueError("preregistration-096 evidence artifact hash mismatch")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("provenance", {}).get("manifest_sha256") != manifest_sha256:
        raise ValueError("source evidence corpus identity mismatch")
    if data.get("evidence_gate", {}).get("passed") is not False:
        raise ValueError("source evidence does not record the frozen failed gate")
    if data.get("evidence_metrics", {}).get("suffix_in_code4_top100_queries") != 34:
        raise ValueError("source evidence does not support the hybrid-policy mechanism")


def hybrid_rankings(
    code4_ranking: list[int], context4_ranking: list[int]
) -> tuple[list[int], list[int], int, int]:
    """Preserve Code 4 top 10, then add one promotion and one Code 4-unique candidate."""

    if len(code4_ranking) < 100:
        raise ValueError("Code 4 ranking must contain the frozen top 100")
    protected = list(code4_ranking[:PROTECTED_PREFIX_K])
    protected_set = set(protected)
    promotion = next((index for index in context4_ranking if index not in protected_set), None)
    if promotion is None:
        raise ValueError("Context 4 ranking did not provide a promotion candidate")
    code4_top100 = set(code4_ranking[:100])
    novel = next(
        (index for index in context4_ranking if index not in code4_top100 and index != promotion),
        None,
    )
    if novel is None:
        raise ValueError("Context 4 ranking did not provide a Code 4-unique candidate")
    return list(code4_ranking[:EVIDENCE_K]), protected + [promotion, novel], promotion, novel


def _window_record(rank: int, index: int, windows, *, source: str) -> dict[str, object]:
    window = windows[index]
    return {
        "rank": rank,
        "index": index,
        "source_path": window.doc,
        "text_sha256": hashlib.sha256(window.text.encode("utf-8")).hexdigest(),
        "selection_source": source,
    }


def evaluate_gate(rows: list[dict[str, object]]) -> tuple[dict[str, object], dict[str, bool]]:
    if len(rows) != 34:
        raise ValueError(f"expected 34 task rows, received {len(rows)}")
    novel_relevant = sum(bool(row["novel_slot_relevant"]) for row in rows)
    new_relevant = sum(bool(row["treatment_new_relevant_vs_control"]) for row in rows)
    control_tokens = statistics.fmean(int(row["control_tokens"]) for row in rows)
    treatment_tokens = statistics.fmean(int(row["treatment_tokens"]) for row in rows)
    token_ratio = treatment_tokens / control_tokens if control_tokens else 1.0
    gates = {
        "g1_twelve_windows_each": all(
            int(row["control_count"]) == EVIDENCE_K and int(row["treatment_count"]) == EVIDENCE_K
            for row in rows
        ),
        "g2_protected_prefix_identical": all(bool(row["prefix_identical"]) for row in rows),
        "g3_valid_distinct_hybrid_slots": all(
            bool(row["promotion_absent_from_prefix"])
            and bool(row["novel_absent_from_code4_top100"])
            and bool(row["suffix_distinct"])
            for row in rows
        ),
        "g4_code4_recall10_34_of_34": sum(bool(row["control_recall_at_10"]) for row in rows) == 34,
        "g5_no_recall_or_shard_loss_at_12": all(
            (not bool(row["control_recall_at_12"]) or bool(row["treatment_recall_at_12"]))
            and (
                not bool(row["control_all_shards_at_12"])
                or bool(row["treatment_all_shards_at_12"])
            )
            for row in rows
        ),
        "g6_novel_slot_relevant_at_least_8": novel_relevant >= 8,
        "g7_new_relevant_vs_control_at_least_8": new_relevant >= 8,
        "g8_mean_tokens_within_10_percent": abs(token_ratio - 1.0) <= 0.10,
    }
    metrics = {
        "queries": len(rows),
        "control_source_recall_at_10": sum(bool(row["control_recall_at_10"]) for row in rows),
        "control_source_recall_at_12": sum(bool(row["control_recall_at_12"]) for row in rows),
        "treatment_source_recall_at_12": sum(bool(row["treatment_recall_at_12"]) for row in rows),
        "control_complete_shards_at_12": sum(
            bool(row["control_all_shards_at_12"]) for row in rows
        ),
        "treatment_complete_shards_at_12": sum(
            bool(row["treatment_all_shards_at_12"]) for row in rows
        ),
        "promotion_slot_relevant_queries": sum(
            bool(row["promotion_slot_relevant"]) for row in rows
        ),
        "novel_slot_relevant_queries": novel_relevant,
        "new_relevant_vs_control_queries": new_relevant,
        "mean_control_tokens": control_tokens,
        "mean_treatment_tokens": treatment_tokens,
        "treatment_control_token_ratio": token_ratio,
    }
    return metrics, {**gates, "passed": all(gates.values())}


def _git_head(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build_evidence(corpus_root: Path, *, max_tokens_per_model: int) -> dict[str, object]:
    if max_tokens_per_model > FROZEN_MAX_TOKENS_PER_MODEL:
        raise ValueError("preregistration 097 caps document tokens at 500,000 per model")
    root = Path(__file__).resolve().parents[1]
    manifest = CorpusManifest.load(corpus_root)
    manifest.verify()
    manifest_sha = _sha256_file(corpus_root / "manifest.json")
    validate_source_evidence(root, manifest_sha)
    windows = load_windows(corpus_root)
    documents = {window.doc for window in windows}

    lexical_started = time.perf_counter()
    lexical = BM25(windows)
    lexical_build_ms = (time.perf_counter() - lexical_started) * 1000.0
    code_started = time.perf_counter()
    code4 = Voyage(windows, DEFAULT_CONTROL_MODEL, max_tokens_per_model)
    code_build_ms = (time.perf_counter() - code_started) * 1000.0
    context_started = time.perf_counter()
    context4 = VoyageContext4(windows, DEFAULT_TREATMENT_MODEL, max_tokens_per_model)
    context_build_ms = (time.perf_counter() - context_started) * 1000.0

    tasks: list[dict[str, object]] = []
    gate_rows: list[dict[str, object]] = []
    query_latency_ms: list[dict[str, float]] = []
    for task in sorted(discover_tasks(), key=lambda item: item.task_id):
        gold_docs = {path for path in documents if path.startswith(f"sessions/{task.task_id}/")}
        if not gold_docs:
            continue
        gold_windows = {index for index, window in enumerate(windows) if window.doc in gold_docs}
        started = time.perf_counter()
        lexical_ranking = rank_scores(lexical.scores(task.prompt), DEFAULT_CANDIDATE_K)
        lexical_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        code_ranking = fused_ranking(
            code4.scores(task.prompt), lexical_ranking, result_k=DEFAULT_CANDIDATE_K
        )
        code_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        context_ranking = fused_ranking(
            context4.scores(task.prompt), lexical_ranking, result_k=DEFAULT_CANDIDATE_K
        )
        context_ms = (time.perf_counter() - started) * 1000.0
        control, treatment, promotion, novel = hybrid_rankings(code_ranking, context_ranking)

        control_docs = {windows[index].doc for index in control} & gold_docs
        treatment_docs = {windows[index].doc for index in treatment} & gold_docs
        treatment_new_relevant = sorted((set(treatment) & gold_windows) - set(control))
        control_tokens = estimate_tokens([windows[index].text for index in control])
        treatment_tokens = estimate_tokens([windows[index].text for index in treatment])
        gate_row: dict[str, object] = {
            "task_id": task.task_id,
            "control_count": len(control),
            "treatment_count": len(treatment),
            "prefix_identical": control[:PROTECTED_PREFIX_K] == treatment[:PROTECTED_PREFIX_K],
            "promotion_absent_from_prefix": promotion not in code_ranking[:PROTECTED_PREFIX_K],
            "novel_absent_from_code4_top100": novel not in code_ranking[:100],
            "suffix_distinct": promotion != novel,
            "control_recall_at_10": bool(first_gold_rank(control[:10], gold_windows)),
            "control_recall_at_12": bool(first_gold_rank(control, gold_windows)),
            "treatment_recall_at_12": bool(first_gold_rank(treatment, gold_windows)),
            "control_all_shards_at_12": bool(gold_docs and control_docs == gold_docs),
            "treatment_all_shards_at_12": bool(gold_docs and treatment_docs == gold_docs),
            "promotion_slot_relevant": promotion in gold_windows,
            "novel_slot_relevant": novel in gold_windows,
            "treatment_new_relevant_vs_control": bool(treatment_new_relevant),
            "control_tokens": control_tokens,
            "treatment_tokens": treatment_tokens,
        }
        gate_rows.append(gate_row)
        tasks.append(
            {
                "task_id": task.task_id,
                "query_sha256": sha256_text(task.prompt),
                "gold_documents": sorted(gold_docs),
                "rankings": {
                    "code4_top100": code_ranking,
                    "context4_top100": context_ranking,
                },
                "diagnostics": {
                    **gate_row,
                    "promotion_index": promotion,
                    "novel_index": novel,
                    "promotion_context4_rank": context_ranking.index(promotion) + 1,
                    "promotion_code4_rank": (
                        code_ranking.index(promotion) + 1 if promotion in code_ranking else None
                    ),
                    "novel_context4_rank": context_ranking.index(novel) + 1,
                    "treatment_new_relevant_indices": treatment_new_relevant,
                },
                CONTROL_ARM: {
                    "model": DEFAULT_CONTROL_MODEL,
                    "windows": [
                        _window_record(rank, index, windows, source="code4")
                        for rank, index in enumerate(control, start=1)
                    ],
                },
                TREATMENT_ARM: {
                    "model": "voyage-code-4+voyage-context-4-hybrid-suffix",
                    "windows": [
                        _window_record(
                            rank,
                            index,
                            windows,
                            source=(
                                "code4"
                                if rank <= PROTECTED_PREFIX_K
                                else "context4_promotion"
                                if rank == 11
                                else "context4_code4_unique"
                            ),
                        )
                        for rank, index in enumerate(treatment, start=1)
                    ],
                },
            }
        )
        query_latency_ms.append(
            {
                "lexical": round(lexical_ms, 3),
                "code4": round(code_ms, 3),
                "context4": round(context_ms, 3),
            }
        )

    metrics, gate = evaluate_gate(gate_rows)
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT,
        "measured_at": datetime.now(UTC).isoformat(),
        "provenance": {
            "git_head": _git_head(root),
            "manifest_sha256": manifest_sha,
            "script_sha256": _sha256_file(Path(__file__)),
            "source_evidence_sha256": SOURCE_EVIDENCE_SHA256,
            "corpus_sessions": len(manifest.sessions),
            "raw_windows": len(windows),
        },
        "configuration": {
            "code_model": DEFAULT_CONTROL_MODEL,
            "context_model": DEFAULT_TREATMENT_MODEL,
            "context_grouping": "ordered_raw_windows_by_manifest_session",
            "candidate_k_per_leg": DEFAULT_CANDIDATE_K,
            "protected_prefix_k": PROTECTED_PREFIX_K,
            "evidence_k": EVIDENCE_K,
            "suffix_policy": "first_context_outside_prefix_then_first_remaining_outside_code4_top100",
            "rrf_k": RRF_K,
            "window_words": WINDOW_WORDS,
            "window_stride": WINDOW_STRIDE,
            "max_tokens_per_model": max_tokens_per_model,
        },
        "add_time_ms": {
            "lexical": round(lexical_build_ms, 3),
            "code4": round(code_build_ms, 3),
            "context4": round(context_build_ms, 3),
        },
        "context_grouping_diagnostics": context4.grouping_diagnostics,
        "query_latency_ms": query_latency_ms,
        "evidence_metrics": metrics,
        "evidence_gate": gate,
        "tasks": tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--max-tokens-per-model", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to replace one-shot evidence artifact {args.out}")
    artifact = build_evidence(args.corpus, max_tokens_per_model=args.max_tokens_per_model)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "evidence_metrics": artifact["evidence_metrics"],
                "evidence_gate": artifact["evidence_gate"],
            },
            indent=2,
        )
    )
    return 0 if artifact["evidence_gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
