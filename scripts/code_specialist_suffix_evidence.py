"""Build the one-shot protected Code 4 plus Context 4 evidence artifact."""

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

EXPERIMENT = "096-code4-context4-protected-suffix-evidence"
SOURCE_SCREEN_SHA256 = "4deadffe747453a256e8da46dad83d38d95b6fb8ce6b0aad981870cbdb886389"
SOURCE_SCREEN_PATH = Path("results/retrieval/095-voyage-context4-direct-replacement.json")
CONTROL_ARM = "code4_12_replay"
TREATMENT_ARM = "code4_context4_suffix_12_replay"
PROTECTED_PREFIX_K = 10
EVIDENCE_K = 12
SUFFIX_K = EVIDENCE_K - PROTECTED_PREFIX_K


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_source_screen(root: Path, manifest_sha256: str) -> None:
    path = root / SOURCE_SCREEN_PATH
    if _sha256_file(path) != SOURCE_SCREEN_SHA256:
        raise ValueError("preregistration-095 source-screen artifact hash mismatch")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("provenance", {}).get("manifest_sha256") != manifest_sha256:
        raise ValueError("source-screen corpus identity does not match this evidence build")
    if data.get("decision", {}).get("protected_fusion_preregistration_licensed") is not True:
        raise ValueError("source screen did not license protected fusion")


def protected_rankings(
    code4_ranking: list[int], context4_ranking: list[int]
) -> tuple[list[int], list[int], list[int]]:
    """Return equal-sized control and treatment lists with an immutable Code 4 prefix."""

    if len(code4_ranking) < EVIDENCE_K:
        raise ValueError(f"Code 4 ranking must contain at least {EVIDENCE_K} candidates")
    protected = list(code4_ranking[:PROTECTED_PREFIX_K])
    suffix: list[int] = []
    protected_set = set(protected)
    for index in context4_ranking:
        if index in protected_set or index in suffix:
            continue
        suffix.append(index)
        if len(suffix) == SUFFIX_K:
            break
    if len(suffix) != SUFFIX_K:
        raise ValueError("Context 4 ranking did not provide two unique suffix candidates")
    return list(code4_ranking[:EVIDENCE_K]), protected + suffix, suffix


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
    relevant_suffix_queries = sum(bool(row["treatment_suffix_has_relevant"]) for row in rows)
    new_relevant_queries = sum(bool(row["treatment_new_relevant_vs_control"]) for row in rows)
    control_tokens = statistics.fmean(int(row["control_tokens"]) for row in rows)
    treatment_tokens = statistics.fmean(int(row["treatment_tokens"]) for row in rows)
    token_ratio = treatment_tokens / control_tokens if control_tokens else 1.0
    gates = {
        "g1_twelve_windows_each": all(
            int(row["control_count"]) == EVIDENCE_K and int(row["treatment_count"]) == EVIDENCE_K
            for row in rows
        ),
        "g2_protected_prefix_identical": all(bool(row["prefix_identical"]) for row in rows),
        "g3_two_unique_context_suffix_windows": all(
            int(row["treatment_suffix_count"]) == SUFFIX_K and bool(row["treatment_unique"])
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
        "g6_relevant_context_suffix_at_least_12": relevant_suffix_queries >= 12,
        "g7_new_relevant_vs_control_at_least_8": new_relevant_queries >= 8,
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
        "relevant_context_suffix_queries": relevant_suffix_queries,
        "new_relevant_vs_control_queries": new_relevant_queries,
        "suffix_in_code4_top100_queries": sum(
            bool(row["any_suffix_in_code4_top100"]) for row in rows
        ),
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
        raise ValueError("preregistration 096 caps document tokens at 500,000 per model")
    root = Path(__file__).resolve().parents[1]
    manifest = CorpusManifest.load(corpus_root)
    manifest.verify()
    manifest_sha = _sha256_file(corpus_root / "manifest.json")
    validate_source_screen(root, manifest_sha)
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
        control, treatment, suffix = protected_rankings(code_ranking, context_ranking)

        control_docs = {windows[index].doc for index in control} & gold_docs
        treatment_docs = {windows[index].doc for index in treatment} & gold_docs
        treatment_suffix_relevant = [index for index in suffix if index in gold_windows]
        treatment_new_relevant = sorted((set(treatment) & gold_windows) - set(control))
        control_tokens = estimate_tokens([windows[index].text for index in control])
        treatment_tokens = estimate_tokens([windows[index].text for index in treatment])
        gate_row: dict[str, object] = {
            "task_id": task.task_id,
            "control_count": len(control),
            "treatment_count": len(treatment),
            "prefix_identical": control[:PROTECTED_PREFIX_K] == treatment[:PROTECTED_PREFIX_K],
            "treatment_suffix_count": len(suffix),
            "treatment_unique": len(set(treatment)) == len(treatment),
            "control_recall_at_10": bool(first_gold_rank(control[:10], gold_windows)),
            "control_recall_at_12": bool(first_gold_rank(control, gold_windows)),
            "treatment_recall_at_12": bool(first_gold_rank(treatment, gold_windows)),
            "control_all_shards_at_12": bool(gold_docs and control_docs == gold_docs),
            "treatment_all_shards_at_12": bool(gold_docs and treatment_docs == gold_docs),
            "treatment_suffix_has_relevant": bool(treatment_suffix_relevant),
            "treatment_new_relevant_vs_control": bool(treatment_new_relevant),
            "any_suffix_in_code4_top100": bool(set(suffix) & set(code_ranking)),
            "control_tokens": control_tokens,
            "treatment_tokens": treatment_tokens,
        }
        gate_rows.append(gate_row)
        tasks.append(
            {
                "task_id": task.task_id,
                "query_sha256": sha256_text(task.prompt),
                "gold_documents": sorted(gold_docs),
                "diagnostics": {
                    **gate_row,
                    "treatment_suffix_indices": suffix,
                    "treatment_suffix_relevant_indices": treatment_suffix_relevant,
                    "treatment_new_relevant_indices": treatment_new_relevant,
                    "treatment_suffix_code4_ranks": [
                        code_ranking.index(index) + 1 if index in code_ranking else None
                        for index in suffix
                    ],
                    "code4_first_relevant_rank": first_gold_rank(code_ranking, gold_windows),
                    "context4_first_relevant_rank": first_gold_rank(context_ranking, gold_windows),
                },
                CONTROL_ARM: {
                    "model": DEFAULT_CONTROL_MODEL,
                    "windows": [
                        _window_record(rank, index, windows, source="code4")
                        for rank, index in enumerate(control, start=1)
                    ],
                },
                TREATMENT_ARM: {
                    "model": "voyage-code-4+voyage-context-4-protected-suffix",
                    "windows": [
                        _window_record(
                            rank,
                            index,
                            windows,
                            source="code4" if rank <= PROTECTED_PREFIX_K else "context4",
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
            "source_screen_sha256": SOURCE_SCREEN_SHA256,
            "corpus_sessions": len(manifest.sessions),
            "raw_windows": len(windows),
        },
        "configuration": {
            "code_model": DEFAULT_CONTROL_MODEL,
            "context_model": DEFAULT_TREATMENT_MODEL,
            "context_grouping": "ordered_raw_windows_by_manifest_session",
            "candidate_k_per_leg": DEFAULT_CANDIDATE_K,
            "protected_prefix_k": PROTECTED_PREFIX_K,
            "suffix_k": SUFFIX_K,
            "evidence_k": EVIDENCE_K,
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
