"""Paired retrieval screen for replacing Voyage Code 3 with Voyage Code 4.

The experiment is frozen in ``preregistration/090-voyage-code4-direct-replacement.md``.
Both arms use the same raw windows, BM25 ranking, RRF constant, and result budget. The two
embedding models are never fused with each other.

Run the paid embedding calls only on the designated embedding host::

    python -m scripts.code_embedding_replacement_experiment --corpus corpus \
        --max-tokens-per-model 500000 \
        --out results/retrieval/090-voyage-code4-direct-replacement.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from harness.adapters.base import CorpusManifest
from harness.tasks import discover_tasks
from scripts.retrieval_probe import BM25, Voyage, estimate_tokens, load_windows

RRF_K = 60
DEFAULT_CANDIDATE_K = 100
DEFAULT_RESULT_K = 100
DEFAULT_CONTROL_MODEL = "voyage-code-3"
DEFAULT_TREATMENT_MODEL = "voyage-code-4"
FROZEN_MAX_TOKENS_PER_MODEL = 500_000
EVALUATION_K = (1, 3, 5, 10, 20, 100)


def rank_scores(scores: Mapping[int, float], limit: int) -> list[int]:
    """Return a deterministic descending ranking with window index as the tie-breaker."""

    return [index for index, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def rrf(rankings: Sequence[Sequence[int]], *, limit: int) -> list[int]:
    """Fuse independent dense and lexical ranks without comparing their raw scores."""

    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking, start=1):
            scores[index] = scores.get(index, 0.0) + 1.0 / (RRF_K + rank)
    return rank_scores(scores, limit)


def fused_ranking(
    dense_scores: Mapping[int, float],
    lexical_ranking: Sequence[int],
    *,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    result_k: int = DEFAULT_RESULT_K,
) -> list[int]:
    """Build one model arm from its own dense ranking plus the frozen shared lexical rank."""

    dense_ranking = rank_scores(dense_scores, candidate_k)
    return rrf([dense_ranking, lexical_ranking[:candidate_k]], limit=result_k)


def first_gold_rank(ranking: Sequence[int], gold: set[int]) -> int | None:
    for rank, index in enumerate(ranking, start=1):
        if index in gold:
            return rank
    return None


def nearest_percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def validate_frozen_configuration(
    *,
    control_model: str,
    treatment_model: str,
    max_tokens_per_model: int,
    candidate_k: int,
    result_k: int,
) -> None:
    """Refuse runtime changes that would violate preregistration 090."""

    if control_model != DEFAULT_CONTROL_MODEL or treatment_model != DEFAULT_TREATMENT_MODEL:
        raise ValueError(
            "preregistration 090 fixes voyage-code-3 as control and voyage-code-4 as treatment"
        )
    if max_tokens_per_model > FROZEN_MAX_TOKENS_PER_MODEL:
        raise ValueError("preregistration 090 caps document tokens at 500,000 per model")
    if candidate_k != DEFAULT_CANDIDATE_K or result_k != DEFAULT_RESULT_K:
        raise ValueError("preregistration 090 fixes candidate_k and result_k at 100")


def _rank_relation(control_rank: int | None, treatment_rank: int | None) -> str:
    if control_rank == treatment_rank:
        return "tie"
    if treatment_rank is None:
        return "regression"
    if control_rank is None or treatment_rank < control_rank:
        return "win"
    return "regression"


def compare_rankings(
    control: Sequence[int],
    treatment: Sequence[int],
    gold_windows: set[int],
    *,
    result_k: int = DEFAULT_RESULT_K,
) -> dict[str, object]:
    """Return paired rank and candidate-novelty diagnostics for one query."""

    control = list(control[:result_k])
    treatment = list(treatment[:result_k])
    control_set = set(control)
    treatment_set = set(treatment)
    union = control_set | treatment_set
    overlap = control_set & treatment_set
    control_rank = first_gold_rank(control, gold_windows)
    treatment_rank = first_gold_rank(treatment, gold_windows)
    row: dict[str, object] = {
        "control_rank": control_rank,
        "treatment_rank": treatment_rank,
        "rank_relation": _rank_relation(control_rank, treatment_rank),
        "treatment_new_relevant_windows": sorted((treatment_set & gold_windows) - control_set),
        "control_new_relevant_windows": sorted((control_set & gold_windows) - treatment_set),
        "top100_overlap": len(overlap),
        "top100_union": len(union),
        "top100_jaccard": len(overlap) / len(union) if union else 1.0,
    }
    for k in EVALUATION_K:
        row[f"control_recall_at_{k}"] = bool(control_rank and control_rank <= k)
        row[f"treatment_recall_at_{k}"] = bool(treatment_rank and treatment_rank <= k)
    return row


def _outcome_counts(rows: Sequence[Mapping[str, object]], k: int) -> dict[str, int]:
    wins = ties = regressions = 0
    for row in rows:
        control = bool(row[f"control_recall_at_{k}"])
        treatment = bool(row[f"treatment_recall_at_{k}"])
        if treatment and not control:
            wins += 1
        elif control and not treatment:
            regressions += 1
        else:
            ties += 1
    return {"wins": wins, "ties": ties, "regressions": regressions}


def summarize(
    rows: Sequence[Mapping[str, object]],
    *,
    control_latency: Sequence[float],
    treatment_latency: Sequence[float],
) -> tuple[dict[str, object], dict[str, bool], dict[str, bool]]:
    """Aggregate paired endpoints and evaluate the frozen predictions and gates."""

    if not rows:
        raise ValueError("cannot summarize an empty query roster")
    queries = len(rows)
    recall: dict[str, dict[str, object]] = {}
    for k in EVALUATION_K:
        control_count = sum(bool(row[f"control_recall_at_{k}"]) for row in rows)
        treatment_count = sum(bool(row[f"treatment_recall_at_{k}"]) for row in rows)
        recall[f"at_{k}"] = {
            "control_count": control_count,
            "treatment_count": treatment_count,
            "control": control_count / queries,
            "treatment": treatment_count / queries,
            "delta_queries": treatment_count - control_count,
            "paired": _outcome_counts(rows, k),
        }

    control_mrr = statistics.fmean(
        0.0 if row["control_rank"] is None else 1.0 / int(row["control_rank"])
        for row in rows
    )
    treatment_mrr = statistics.fmean(
        0.0 if row["treatment_rank"] is None else 1.0 / int(row["treatment_rank"])
        for row in rows
    )
    rank_relations = {
        relation: sum(row["rank_relation"] == relation for row in rows)
        for relation in ("win", "tie", "regression")
    }
    treatment_new_queries = sum(bool(row["treatment_new_relevant_windows"]) for row in rows)
    control_new_queries = sum(bool(row["control_new_relevant_windows"]) for row in rows)
    control_tokens = statistics.fmean(int(row["control_response_tokens_at_100"]) for row in rows)
    treatment_tokens = statistics.fmean(
        int(row["treatment_response_tokens_at_100"]) for row in rows
    )
    token_ratio = treatment_tokens / control_tokens if control_tokens else 1.0
    control_p95 = nearest_percentile(control_latency, 0.95)
    treatment_p95 = nearest_percentile(treatment_latency, 0.95)

    metrics: dict[str, object] = {
        "queries": queries,
        "source_recall": recall,
        "mrr": {
            "control": control_mrr,
            "treatment": treatment_mrr,
            "delta": treatment_mrr - control_mrr,
        },
        "first_relevant_rank": rank_relations,
        "candidate_novelty": {
            "treatment_new_relevant_queries": treatment_new_queries,
            "control_new_relevant_queries": control_new_queries,
            "mean_top100_jaccard": statistics.fmean(float(row["top100_jaccard"]) for row in rows),
        },
        "latency_ms": {
            "control_median": statistics.median(control_latency),
            "control_p95": control_p95,
            "treatment_median": statistics.median(treatment_latency),
            "treatment_p95": treatment_p95,
            "p95_ratio": treatment_p95 / control_p95 if control_p95 else None,
        },
        "mean_response_tokens_at_100": {
            "control": control_tokens,
            "treatment": treatment_tokens,
            "ratio": token_ratio,
        },
    }

    recall10_delta = int(recall["at_10"]["delta_queries"])
    recall100_delta = int(recall["at_100"]["delta_queries"])
    mrr_delta = treatment_mrr - control_mrr
    predictions = {
        "p1_recall10_plus_2": recall10_delta >= 2,
        "p2_mrr_plus_0_03": mrr_delta >= 0.03,
        "p3_recall100_non_decrease": recall100_delta >= 0,
        "p4_rank_wins_exceed_regressions": rank_relations["win"] > rank_relations["regression"],
        "p5_new_relevant_queries_at_least_3": treatment_new_queries >= 3,
        "p6_response_tokens_within_5_percent": abs(token_ratio - 1.0) <= 0.05,
        "p7_treatment_p95_below_2x_control": bool(control_p95 and treatment_p95 < 2 * control_p95),
    }
    early_gate = (
        (recall10_delta >= 2 and mrr_delta >= 0.0)
        or (mrr_delta >= 0.03 and recall10_delta >= 0)
    )
    decisions = {
        "direct_replacement_passed": bool(
            predictions["p3_recall100_non_decrease"]
            and predictions["p4_rank_wins_exceed_regressions"]
            and early_gate
        ),
        "protected_rescue_preregistration_licensed": predictions[
            "p5_new_relevant_queries_at_least_3"
        ],
        "task_solve_screen_licensed": False,
    }
    decisions["task_solve_screen_licensed"] = decisions["direct_replacement_passed"]
    return metrics, predictions, decisions


def _git_head(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run_experiment(
    corpus_root: Path,
    *,
    control_model: str = DEFAULT_CONTROL_MODEL,
    treatment_model: str = DEFAULT_TREATMENT_MODEL,
    max_tokens_per_model: int,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    result_k: int = DEFAULT_RESULT_K,
) -> dict[str, object]:
    validate_frozen_configuration(
        control_model=control_model,
        treatment_model=treatment_model,
        max_tokens_per_model=max_tokens_per_model,
        candidate_k=candidate_k,
        result_k=result_k,
    )
    manifest = CorpusManifest.load(corpus_root)
    manifest.verify()
    windows = load_windows(corpus_root)
    if not windows:
        raise ValueError("corpus produced no raw evidence windows")
    documents = {window.doc for window in windows}

    lexical_started = time.perf_counter()
    lexical = BM25(windows)
    lexical_build_ms = (time.perf_counter() - lexical_started) * 1000.0
    control_started = time.perf_counter()
    control_dense = Voyage(windows, control_model, max_tokens_per_model)
    control_build_ms = (time.perf_counter() - control_started) * 1000.0
    treatment_started = time.perf_counter()
    treatment_dense = Voyage(windows, treatment_model, max_tokens_per_model)
    treatment_build_ms = (time.perf_counter() - treatment_started) * 1000.0

    rows: list[dict[str, object]] = []
    control_latency: list[float] = []
    treatment_latency: list[float] = []
    for task in sorted(discover_tasks(), key=lambda item: item.task_id):
        gold_docs = {path for path in documents if path.startswith(f"sessions/{task.task_id}/")}
        if not gold_docs:
            continue
        gold_windows = {
            index for index, window in enumerate(windows) if window.doc in gold_docs
        }

        lexical_started = time.perf_counter()
        lexical_ranking = rank_scores(lexical.scores(task.prompt), candidate_k)
        lexical_ms = (time.perf_counter() - lexical_started) * 1000.0

        control_started = time.perf_counter()
        control = fused_ranking(
            control_dense.scores(task.prompt),
            lexical_ranking,
            candidate_k=candidate_k,
            result_k=result_k,
        )
        control_ms = lexical_ms + (time.perf_counter() - control_started) * 1000.0

        treatment_started = time.perf_counter()
        treatment = fused_ranking(
            treatment_dense.scores(task.prompt),
            lexical_ranking,
            candidate_k=candidate_k,
            result_k=result_k,
        )
        treatment_ms = lexical_ms + (time.perf_counter() - treatment_started) * 1000.0

        row = {
            "task_id": task.task_id,
            **compare_rankings(control, treatment, gold_windows, result_k=result_k),
            "control_response_tokens_at_10": estimate_tokens(
                [windows[index].text for index in control[:10]]
            ),
            "treatment_response_tokens_at_10": estimate_tokens(
                [windows[index].text for index in treatment[:10]]
            ),
            "control_response_tokens_at_100": estimate_tokens(
                [windows[index].text for index in control[:100]]
            ),
            "treatment_response_tokens_at_100": estimate_tokens(
                [windows[index].text for index in treatment[:100]]
            ),
            "shared_lexical_ms": round(lexical_ms, 3),
            "control_total_ms": round(control_ms, 3),
            "treatment_total_ms": round(treatment_ms, 3),
        }
        rows.append(row)
        control_latency.append(control_ms)
        treatment_latency.append(treatment_ms)

    metrics, predictions, decisions = summarize(
        rows,
        control_latency=control_latency,
        treatment_latency=treatment_latency,
    )
    root = Path(__file__).resolve().parents[1]
    manifest_sha = hashlib.sha256((corpus_root / "manifest.json").read_bytes()).hexdigest()
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "experiment": "090-voyage-code4-direct-replacement",
        "measured_at": datetime.now(UTC).isoformat(),
        "provenance": {
            "git_head": _git_head(root),
            "manifest_sha256": manifest_sha,
            "script_sha256": script_sha,
            "corpus_sessions": len(manifest.sessions),
            "raw_windows": len(windows),
        },
        "configuration": {
            "control_model": control_model,
            "treatment_model": treatment_model,
            "candidate_k_per_leg": candidate_k,
            "result_k": result_k,
            "rrf_k": RRF_K,
            "window_words": 160,
            "window_stride": 120,
            "max_tokens_per_model": max_tokens_per_model,
        },
        "add_time_ms": {
            "lexical": round(lexical_build_ms, 3),
            "control_dense": round(control_build_ms, 3),
            "treatment_dense": round(treatment_build_ms, 3),
        },
        "metrics": metrics,
        "predictions": predictions,
        "decision": decisions,
        "per_task": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--control-model", default=DEFAULT_CONTROL_MODEL)
    parser.add_argument("--treatment-model", default=DEFAULT_TREATMENT_MODEL)
    parser.add_argument("--max-tokens-per-model", type=int, required=True)
    parser.add_argument("--candidate-k", type=int, default=DEFAULT_CANDIDATE_K)
    parser.add_argument("--result-k", type=int, default=DEFAULT_RESULT_K)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(
        args.corpus,
        control_model=args.control_model,
        treatment_model=args.treatment_model,
        max_tokens_per_model=args.max_tokens_per_model,
        candidate_k=args.candidate_k,
        result_k=args.result_k,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "metrics": result["metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
