"""Paired retrieval screen for Code 4 versus session-aware Context 4.

The experiment is frozen in
``preregistration/095-voyage-context4-direct-replacement.md``. Each model is fused only with
the shared BM25 ranking. Their raw scores and vectors are never compared with each other.

Run paid calls only on the designated embedding host::

    python -m scripts.code_context4_replacement_experiment --corpus corpus \
        --max-tokens-per-model 500000 \
        --out results/retrieval/095-voyage-context4-direct-replacement.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness.adapters.base import CorpusManifest
from harness.tasks import discover_tasks
from scripts.code_embedding_replacement_experiment import (
    EVALUATION_K,
    fused_ranking,
    nearest_percentile,
    rank_scores,
)
from scripts.retrieval_probe import BM25, Voyage, Window, estimate_tokens, load_windows

DEFAULT_CONTROL_MODEL = "voyage-code-4"
DEFAULT_TREATMENT_MODEL = "voyage-context-4"
DEFAULT_CANDIDATE_K = 100
DEFAULT_RESULT_K = 100
FROZEN_MAX_TOKENS_PER_MODEL = 500_000
OUTPUT_DIMENSION = 1024
MAX_REQUEST_CHARS = 60_000
MAX_REQUEST_CHUNKS = 1_000


@dataclass(frozen=True)
class DocumentPart:
    """One session-local request group with stable global window indices."""

    doc: str
    indices: tuple[int, ...]
    texts: tuple[str, ...]


def document_parts(
    windows: Sequence[Window],
    *,
    max_request_chars: int = MAX_REQUEST_CHARS,
    max_request_chunks: int = MAX_REQUEST_CHUNKS,
) -> list[DocumentPart]:
    """Group ordered windows by session, splitting only between windows when required."""

    if max_request_chars < 1 or max_request_chunks < 1:
        raise ValueError("Context 4 request limits must be positive")
    by_doc: dict[str, list[tuple[int, str]]] = {}
    for index, window in enumerate(windows):
        by_doc.setdefault(window.doc, []).append((index, window.text))

    parts: list[DocumentPart] = []
    for doc, indexed_texts in by_doc.items():
        current_indices: list[int] = []
        current_texts: list[str] = []
        current_chars = 0
        for index, text in indexed_texts:
            if len(text) > max_request_chars:
                raise ValueError(
                    f"one raw window in {doc} exceeds the Context 4 request character limit"
                )
            if current_texts and (
                len(current_texts) >= max_request_chunks
                or current_chars + len(text) > max_request_chars
            ):
                parts.append(DocumentPart(doc, tuple(current_indices), tuple(current_texts)))
                current_indices = []
                current_texts = []
                current_chars = 0
            current_indices.append(index)
            current_texts.append(text)
            current_chars += len(text)
        if current_texts:
            parts.append(DocumentPart(doc, tuple(current_indices), tuple(current_texts)))
    return parts


def request_batches(
    parts: Sequence[DocumentPart],
    *,
    max_request_chars: int = MAX_REQUEST_CHARS,
    max_request_chunks: int = MAX_REQUEST_CHUNKS,
) -> list[list[DocumentPart]]:
    """Pack whole document parts into bounded requests without merging their identities."""

    batches: list[list[DocumentPart]] = []
    current: list[DocumentPart] = []
    current_chars = 0
    current_chunks = 0
    for part in parts:
        part_chars = sum(len(text) for text in part.texts)
        part_chunks = len(part.texts)
        if current and (
            current_chars + part_chars > max_request_chars
            or current_chunks + part_chunks > max_request_chunks
        ):
            batches.append(current)
            current = []
            current_chars = 0
            current_chunks = 0
        current.append(part)
        current_chars += part_chars
        current_chunks += part_chunks
    if current:
        batches.append(current)
    return batches


class VoyageContext4:
    """Contextualized Voyage embeddings aligned to the frozen raw windows."""

    name = "voyage-context"

    def __init__(
        self,
        windows: list[Window],
        model: str,
        max_tokens: int,
        *,
        client: Any | None = None,
    ) -> None:
        self.windows = windows
        self.model = model
        texts = [window.text for window in windows]
        estimate = estimate_tokens(texts)
        print(
            f"voyage-context: {len(windows)} windows, about {estimate:,} tokens "
            "to embed (pre-flight)",
            file=sys.stderr,
        )
        Voyage._refuse_over_ceiling(estimate, max_tokens, "pre-flight estimate")

        if client is None:
            try:
                import voyageai
            except ImportError as error:  # pragma: no cover, environment dependent
                raise SystemExit(
                    "the Context 4 screen needs the voyageai client and VOYAGE_API_KEY"
                ) from error
            if not os.environ.get("VOYAGE_API_KEY"):
                raise SystemExit(
                    "VOYAGE_API_KEY is not set. Run this paid screen on the designated host."
                )
            client = voyageai.Client()
        self.client = client

        counted = self._count_tokens(texts)
        if counted is None:
            raise SystemExit(
                "Context 4 vendor token counting is unavailable, so the frozen hard spend "
                "ceiling cannot be established before paid calls"
            )
        print(f"voyage-context: {counted:,} tokens by the vendor tokenizer", file=sys.stderr)
        Voyage._refuse_over_ceiling(counted, max_tokens, "vendor token count")

        try:
            import numpy
        except ImportError as error:  # pragma: no cover, environment dependent
            raise SystemExit("the Context 4 screen needs numpy") from error
        self.numpy = numpy

        parts = document_parts(windows)
        batches = request_batches(parts)
        vectors: list[list[float] | None] = [None] * len(windows)
        for batch_number, batch in enumerate(batches, start=1):
            result = self.client.contextualized_embed(
                inputs=[list(part.texts) for part in batch],
                model=model,
                input_type="document",
                output_dimension=OUTPUT_DIMENSION,
                output_dtype="float",
            )
            response_groups = getattr(result, "results", None)
            if not isinstance(response_groups, list) or len(response_groups) != len(batch):
                raise RuntimeError("Context 4 response changed document-group alignment")
            for part, response_group in zip(batch, response_groups, strict=True):
                embeddings = getattr(response_group, "embeddings", None)
                if not isinstance(embeddings, list) or len(embeddings) != len(part.indices):
                    raise RuntimeError("Context 4 response changed raw-window alignment")
                for index, vector in zip(part.indices, embeddings, strict=True):
                    if not isinstance(vector, list) or len(vector) != OUTPUT_DIMENSION:
                        raise RuntimeError("Context 4 response changed vector width")
                    vectors[index] = [float(value) for value in vector]
            print(
                f"  contextualized request {batch_number:>3} / {len(batches)}",
                file=sys.stderr,
            )
        if any(vector is None for vector in vectors):
            raise RuntimeError("Context 4 response lost one or more raw windows")

        matrix = numpy.asarray(vectors, dtype="float32")
        norms = numpy.linalg.norm(matrix, axis=1, keepdims=True)
        self.matrix = matrix / numpy.where(norms == 0, 1, norms)
        part_counts: dict[str, int] = defaultdict(int)
        for part in parts:
            part_counts[part.doc] += 1
        self.grouping_diagnostics = {
            "documents": len(part_counts),
            "document_parts": len(parts),
            "requests": len(batches),
            "split_documents": sum(count > 1 for count in part_counts.values()),
            "max_request_chars": MAX_REQUEST_CHARS,
            "max_request_chunks": MAX_REQUEST_CHUNKS,
        }

    def _count_tokens(self, texts: list[str]) -> int | None:
        counter = getattr(self.client, "count_tokens", None)
        if counter is None:
            return None
        try:
            return int(counter(texts, model=self.model))
        except Exception as error:  # noqa: BLE001, vendor client errors vary by version
            print(f"voyage-context: count_tokens unavailable ({error})", file=sys.stderr)
            return None

    def scores(self, query: str) -> dict[int, float]:
        result = self.client.contextualized_embed(
            inputs=[query],
            model=self.model,
            input_type="query",
            output_dimension=OUTPUT_DIMENSION,
            output_dtype="float",
        )
        response_groups = getattr(result, "results", None)
        if not isinstance(response_groups, list) or len(response_groups) != 1:
            raise RuntimeError("Context 4 query response did not contain exactly one result")
        embeddings = getattr(response_groups[0], "embeddings", None)
        if not isinstance(embeddings, list) or len(embeddings) != 1:
            raise RuntimeError("Context 4 query response did not contain exactly one vector")
        vector = embeddings[0]
        if not isinstance(vector, list) or len(vector) != OUTPUT_DIMENSION:
            raise RuntimeError("Context 4 query response changed vector width")
        array = self.numpy.asarray(vector, dtype="float32")
        array /= self.numpy.linalg.norm(array) or 1
        return {index: float(value) for index, value in enumerate(self.matrix @ array)}


def validate_frozen_configuration(
    *,
    control_model: str,
    treatment_model: str,
    max_tokens_per_model: int,
    candidate_k: int,
    result_k: int,
) -> None:
    if control_model != DEFAULT_CONTROL_MODEL or treatment_model != DEFAULT_TREATMENT_MODEL:
        raise ValueError("preregistration 095 fixes Code 4 and Context 4 as the two models")
    if max_tokens_per_model > FROZEN_MAX_TOKENS_PER_MODEL:
        raise ValueError("preregistration 095 caps document tokens at 500,000 per model")
    if candidate_k != DEFAULT_CANDIDATE_K or result_k != DEFAULT_RESULT_K:
        raise ValueError("preregistration 095 fixes candidate_k and result_k at 100")


def _rank_relation(control_rank: int | None, treatment_rank: int | None) -> str:
    if control_rank == treatment_rank:
        return "tie"
    if treatment_rank is None:
        return "regression"
    if control_rank is None or treatment_rank < control_rank:
        return "win"
    return "regression"


def first_gold_rank(ranking: Sequence[int], gold: set[int]) -> int | None:
    for rank, index in enumerate(ranking, start=1):
        if index in gold:
            return rank
    return None


def _prefix_comparison(
    control: Sequence[int], treatment: Sequence[int], gold_windows: set[int], k: int
) -> dict[str, object]:
    control_set = set(control[:k])
    treatment_set = set(treatment[:k])
    union = control_set | treatment_set
    return {
        "overlap": len(control_set & treatment_set),
        "union": len(union),
        "jaccard": len(control_set & treatment_set) / len(union) if union else 1.0,
        "treatment_new_relevant_windows": sorted((treatment_set & gold_windows) - control_set),
        "control_new_relevant_windows": sorted((control_set & gold_windows) - treatment_set),
    }


def compare_rankings(
    control: Sequence[int],
    treatment: Sequence[int],
    gold_windows: set[int],
    gold_docs: set[str],
    windows: Sequence[Window],
) -> dict[str, object]:
    control_rank = first_gold_rank(control, gold_windows)
    treatment_rank = first_gold_rank(treatment, gold_windows)
    row: dict[str, object] = {
        "control_rank": control_rank,
        "treatment_rank": treatment_rank,
        "rank_relation": _rank_relation(control_rank, treatment_rank),
    }
    for k in EVALUATION_K:
        row[f"control_recall_at_{k}"] = bool(control_rank and control_rank <= k)
        row[f"treatment_recall_at_{k}"] = bool(treatment_rank and treatment_rank <= k)
    for k in (10, 20, 100):
        row[f"at_{k}"] = _prefix_comparison(control, treatment, gold_windows, k)
        control_docs = {windows[index].doc for index in control[:k]} & gold_docs
        treatment_docs = {windows[index].doc for index in treatment[:k]} & gold_docs
        row[f"control_gold_docs_at_{k}"] = len(control_docs)
        row[f"treatment_gold_docs_at_{k}"] = len(treatment_docs)
        row[f"control_all_shards_at_{k}"] = bool(gold_docs and control_docs == gold_docs)
        row[f"treatment_all_shards_at_{k}"] = bool(gold_docs and treatment_docs == gold_docs)
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
        0.0 if row["control_rank"] is None else 1.0 / int(row["control_rank"]) for row in rows
    )
    treatment_mrr = statistics.fmean(
        0.0 if row["treatment_rank"] is None else 1.0 / int(row["treatment_rank"]) for row in rows
    )
    rank_relations = {
        relation: sum(row["rank_relation"] == relation for row in rows)
        for relation in ("win", "tie", "regression")
    }
    prefix_metrics: dict[str, object] = {}
    for k in (10, 20, 100):
        details = [row[f"at_{k}"] for row in rows]
        prefix_metrics[f"at_{k}"] = {
            "treatment_new_relevant_queries": sum(
                bool(detail["treatment_new_relevant_windows"]) for detail in details
            ),
            "control_new_relevant_queries": sum(
                bool(detail["control_new_relevant_windows"]) for detail in details
            ),
            "mean_overlap": statistics.fmean(float(detail["overlap"]) for detail in details),
            "mean_jaccard": statistics.fmean(float(detail["jaccard"]) for detail in details),
            "control_complete_shards": sum(
                bool(row[f"control_all_shards_at_{k}"]) for row in rows
            ),
            "treatment_complete_shards": sum(
                bool(row[f"treatment_all_shards_at_{k}"]) for row in rows
            ),
        }

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
        "prefix_comparison": prefix_metrics,
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
    predictions = {
        "p1_context_recall10_34_of_34": recall["at_10"]["treatment_count"] == 34,
        "p2_context_mrr_within_minus_0_03": treatment_mrr >= control_mrr - 0.03,
        "p3_context_recall100_34_of_34": recall["at_100"]["treatment_count"] == 34,
        "p4_rank_wins_at_least_regressions": rank_relations["win"] >= rank_relations["regression"],
        "p5_context_new_relevant_top100_at_least_3": prefix_metrics["at_100"][
            "treatment_new_relevant_queries"
        ]
        >= 3,
        "p6_mean_top100_jaccard_below_0_85": prefix_metrics["at_100"]["mean_jaccard"] < 0.85,
        "p7_response_tokens_within_5_percent": abs(token_ratio - 1.0) <= 0.05,
        "p8_context_p95_below_2x_control": bool(control_p95 and treatment_p95 < 2 * control_p95),
    }
    decisions = {
        "direct_replacement_passed": bool(
            predictions["p1_context_recall10_34_of_34"]
            and predictions["p3_context_recall100_34_of_34"]
            and treatment_mrr >= control_mrr
            and rank_relations["win"] > rank_relations["regression"]
        ),
        "protected_fusion_preregistration_licensed": bool(
            predictions["p3_context_recall100_34_of_34"]
            and predictions["p5_context_new_relevant_top100_at_least_3"]
        ),
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
    treatment_dense = VoyageContext4(windows, treatment_model, max_tokens_per_model)
    treatment_build_ms = (time.perf_counter() - treatment_started) * 1000.0

    rows: list[dict[str, object]] = []
    control_latency: list[float] = []
    treatment_latency: list[float] = []
    for task in sorted(discover_tasks(), key=lambda item: item.task_id):
        gold_docs = {path for path in documents if path.startswith(f"sessions/{task.task_id}/")}
        if not gold_docs:
            continue
        gold_windows = {index for index, window in enumerate(windows) if window.doc in gold_docs}

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
            "gold_documents": sorted(gold_docs),
            **compare_rankings(control, treatment, gold_windows, gold_docs, windows),
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
    return {
        "schema_version": 1,
        "experiment": "095-voyage-context4-direct-replacement",
        "measured_at": datetime.now(UTC).isoformat(),
        "provenance": {
            "git_head": _git_head(root),
            "manifest_sha256": hashlib.sha256(
                (corpus_root / "manifest.json").read_bytes()
            ).hexdigest(),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "corpus_sessions": len(manifest.sessions),
            "raw_windows": len(windows),
        },
        "configuration": {
            "control_model": control_model,
            "treatment_model": treatment_model,
            "context_grouping": "ordered_raw_windows_by_manifest_session",
            "context_output_dimension": OUTPUT_DIMENSION,
            "candidate_k_per_leg": candidate_k,
            "result_k": result_k,
            "rrf_k": 60,
            "window_words": 160,
            "window_stride": 120,
            "max_tokens_per_model": max_tokens_per_model,
        },
        "add_time_ms": {
            "lexical": round(lexical_build_ms, 3),
            "control_dense": round(control_build_ms, 3),
            "treatment_dense": round(treatment_build_ms, 3),
        },
        "context_grouping_diagnostics": treatment_dense.grouping_diagnostics,
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
    if args.out.exists():
        raise SystemExit(f"refusing to replace one-shot result artifact {args.out}")
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
