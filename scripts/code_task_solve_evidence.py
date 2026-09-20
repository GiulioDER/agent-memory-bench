"""Build the one-shot ranked evidence artifact frozen by preregistration 091."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from adapters.code_retrieval_replay.adapter import EVIDENCE_K
from harness.adapters.base import CorpusManifest
from harness.memory_prompt import sha256_text
from harness.tasks import discover_tasks
from scripts.code_embedding_replacement_experiment import (
    DEFAULT_CANDIDATE_K,
    DEFAULT_CONTROL_MODEL,
    DEFAULT_RESULT_K,
    DEFAULT_TREATMENT_MODEL,
    RRF_K,
    _git_head,
    compare_rankings,
    fused_ranking,
    rank_scores,
    summarize,
    validate_frozen_configuration,
)
from scripts.retrieval_probe import (
    BM25,
    WINDOW_STRIDE,
    WINDOW_WORDS,
    Voyage,
    estimate_tokens,
    load_windows,
)

EXPERIMENT = "091-voyage-code4-task-solve-evidence"
SOURCE_SCREEN = Path("results/retrieval/090-voyage-code4-direct-replacement.json")
SOURCE_SCREEN_SHA256 = "9ada30c51c6fcbddede0a122d39a3239c05204a661d72a63683ed34d5fcf582a"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_source_screen(root: Path, manifest_sha256: str) -> None:
    path = root / SOURCE_SCREEN
    if _sha256_file(path) != SOURCE_SCREEN_SHA256:
        raise ValueError("preregistration-090 source-screen artifact hash mismatch")
    screen = json.loads(path.read_text(encoding="utf-8"))
    if screen.get("decision", {}).get("task_solve_screen_licensed") is not True:
        raise ValueError("preregistration-090 did not license Task Solve")
    if screen.get("provenance", {}).get("manifest_sha256") != manifest_sha256:
        raise ValueError("source screen and evidence build use different corpus manifests")
    configuration = screen.get("configuration", {})
    if configuration.get("control_model") != DEFAULT_CONTROL_MODEL:
        raise ValueError("source screen control model mismatch")
    if configuration.get("treatment_model") != DEFAULT_TREATMENT_MODEL:
        raise ValueError("source screen treatment model mismatch")


def _window_record(rank: int, index: int, windows) -> dict[str, object]:
    window = windows[index]
    return {
        "rank": rank,
        "index": index,
        "source_path": window.doc,
        "text_sha256": hashlib.sha256(window.text.encode("utf-8")).hexdigest(),
    }


def build_evidence(
    corpus_root: Path,
    *,
    max_tokens_per_model: int,
) -> dict[str, object]:
    validate_frozen_configuration(
        control_model=DEFAULT_CONTROL_MODEL,
        treatment_model=DEFAULT_TREATMENT_MODEL,
        max_tokens_per_model=max_tokens_per_model,
        candidate_k=DEFAULT_CANDIDATE_K,
        result_k=DEFAULT_RESULT_K,
    )
    manifest = CorpusManifest.load(corpus_root)
    manifest.verify()
    windows = load_windows(corpus_root)
    manifest_sha = _sha256_file(corpus_root / "manifest.json")
    root = Path(__file__).resolve().parents[1]
    _validate_source_screen(root, manifest_sha)

    lexical = BM25(windows)
    control_dense = Voyage(windows, DEFAULT_CONTROL_MODEL, max_tokens_per_model)
    treatment_dense = Voyage(windows, DEFAULT_TREATMENT_MODEL, max_tokens_per_model)

    rows: list[dict[str, object]] = []
    task_records: list[dict[str, object]] = []
    control_latency: list[float] = []
    treatment_latency: list[float] = []
    documents = {window.doc for window in windows}
    tasks = [task for task in discover_tasks() if task.kind == "primary"]
    for task in sorted(tasks, key=lambda item: item.task_id):
        gold_docs = {path for path in documents if path.startswith(f"sessions/{task.task_id}/")}
        gold_windows = {
            index for index, window in enumerate(windows) if window.doc in gold_docs
        }
        lexical_ranking = rank_scores(lexical.scores(task.prompt), DEFAULT_CANDIDATE_K)

        started = time.perf_counter()
        control = fused_ranking(control_dense.scores(task.prompt), lexical_ranking)
        control_latency.append((time.perf_counter() - started) * 1000.0)
        started = time.perf_counter()
        treatment = fused_ranking(treatment_dense.scores(task.prompt), lexical_ranking)
        treatment_latency.append((time.perf_counter() - started) * 1000.0)

        row = {
            "task_id": task.task_id,
            **compare_rankings(control, treatment, gold_windows),
            "control_response_tokens_at_100": estimate_tokens(
                [windows[index].text for index in control]
            ),
            "treatment_response_tokens_at_100": estimate_tokens(
                [windows[index].text for index in treatment]
            ),
        }
        rows.append(row)
        task_records.append(
            {
                "task_id": task.task_id,
                "query_sha256": sha256_text(task.prompt),
                "control_first_relevant_rank": row["control_rank"],
                "treatment_first_relevant_rank": row["treatment_rank"],
                "code3_replay": {
                    "model": DEFAULT_CONTROL_MODEL,
                    "windows": [
                        _window_record(rank, index, windows)
                        for rank, index in enumerate(control[:EVIDENCE_K], start=1)
                    ],
                },
                "code4_replay": {
                    "model": DEFAULT_TREATMENT_MODEL,
                    "windows": [
                        _window_record(rank, index, windows)
                        for rank, index in enumerate(treatment[:EVIDENCE_K], start=1)
                    ],
                },
            }
        )

    metrics, predictions, _ = summarize(
        rows,
        control_latency=control_latency,
        treatment_latency=treatment_latency,
    )
    recall10 = metrics["source_recall"]["at_10"]
    rank_relations = metrics["first_relevant_rank"]
    gates = {
        "code4_recall_at_10_at_least_32": recall10["treatment_count"] >= 32,
        "code4_recall_at_10_plus_2": recall10["delta_queries"] >= 2,
        "code4_mrr_non_decrease": metrics["mrr"]["delta"] >= 0.0,
        "rank_wins_exceed_regressions": rank_relations["win"] > rank_relations["regression"],
        "ten_windows_per_task_and_arm": all(
            len(task[arm]["windows"]) == EVIDENCE_K
            for task in task_records
            for arm in ("code3_replay", "code4_replay")
        ),
    }
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT,
        "measured_at": datetime.now(UTC).isoformat(),
        "provenance": {
            "git_head": _git_head(root),
            "manifest_sha256": manifest_sha,
            "builder_sha256": _sha256_file(Path(__file__)),
            "source_screen_path": SOURCE_SCREEN.as_posix(),
            "source_screen_sha256": SOURCE_SCREEN_SHA256,
            "corpus_sessions": len(manifest.sessions),
            "raw_windows": len(windows),
        },
        "configuration": {
            "control_model": DEFAULT_CONTROL_MODEL,
            "treatment_model": DEFAULT_TREATMENT_MODEL,
            "candidate_k_per_leg": DEFAULT_CANDIDATE_K,
            "result_k": DEFAULT_RESULT_K,
            "evidence_k": EVIDENCE_K,
            "rrf_k": RRF_K,
            "window_words": WINDOW_WORDS,
            "window_stride": WINDOW_STRIDE,
            "max_tokens_per_model": max_tokens_per_model,
        },
        "metrics": metrics,
        "source_screen_predictions": predictions,
        "evidence_gate": {"passed": all(gates.values()), "checks": gates},
        "tasks": task_records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--max-tokens-per-model", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to replace one-shot evidence artifact {args.out}")
    result = build_evidence(
        args.corpus,
        max_tokens_per_model=args.max_tokens_per_model,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"evidence_gate": result["evidence_gate"], "metrics": result["metrics"]}, indent=2))
    return 0 if result["evidence_gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
