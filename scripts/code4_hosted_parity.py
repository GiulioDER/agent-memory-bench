"""Replay the pinned Code4 retrieval screen through a hosted AML endpoint.

This verifier reuses the committed corpus and screen implementation. It ingests the exact
``readable_text`` stream, builds an independent NumPy plus canonical BM25 reference from the
vectors persisted by the hosted candidate, and compares all 34 hosted top 100 rankings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from uuid import uuid4

from harness.adapters.base import CorpusManifest, resolve_corpus_path
from harness.tasks import discover_tasks
from scripts.audit_corpus import readable_text
from scripts.code_embedding_replacement_experiment import fused_ranking, rank_scores
from scripts.retrieval_probe import BM25, Window, load_windows

MODEL = "voyage-code-4"
DIMENSION = 1024
TOP_K = 100
POSTGRES_NUL_REPLACEMENT = "\u2400"


@dataclass(frozen=True)
class HttpResult:
    payload: dict[str, Any]
    latency_ms: float


class HostedClient:
    def __init__(self, base_url: str, key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.key = key

    def call(self, path: str, payload: dict[str, Any]) -> HttpResult:
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
        )
        started = time.perf_counter()
        with urlopen(request, timeout=120) as response:
            if response.status != 200:
                raise RuntimeError(f"{path} returned HTTP {response.status}")
            result = json.loads(response.read().decode())
        return HttpResult(result, (time.perf_counter() - started) * 1_000)

    def get(self, path: str) -> dict[str, Any]:
        request = Request(
            self.base_url + path,
            method="GET",
            headers={"Authorization": f"Bearer {self.key}"},
        )
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"{path} returned HTTP {response.status}")
            return json.loads(response.read().decode())


def tenant_for(user_id: str) -> str:
    return "aml_" + hashlib.sha256(user_id.encode()).hexdigest()


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def expected_chunk_id(session_id: str, segment: int, content: str) -> str:
    return "raw_" + canonical_digest(
        {"source_session_id": session_id, "segment": segment, "content": content}
    )


def postgres_safe_window(window: Window) -> Window:
    return Window(doc=window.doc, text=window.text.replace("\x00", POSTGRES_NUL_REPLACEMENT))


def first_gold_rank(ranking: list[int], gold: set[int]) -> int | None:
    for rank, index in enumerate(ranking, start=1):
        if index in gold:
            return rank
    return None


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[position]


def load_persisted_vectors(
    *, dsn: str, table: str, tenant: str
) -> dict[str, Any]:
    import numpy
    import psycopg
    from psycopg import sql

    if not re.fullmatch(r"[a-z_][a-z0-9_]*", table):
        raise ValueError("invalid table identifier")
    query = sql.SQL(
        "SELECT id, embedding::text FROM {} WHERE tenant_id = %s ORDER BY id"
    ).format(sql.Identifier(table))
    with psycopg.connect(dsn) as connection, connection.transaction():
        connection.execute(
            "SELECT set_config('recall.tenant_id', %s, true)", (tenant,)
        )
        rows = connection.execute(query, (tenant,)).fetchall()
    vectors: dict[str, numpy.ndarray] = {}
    for chunk_id, raw_vector in rows:
        vector = numpy.fromstring(str(raw_vector).strip("[]"), sep=",", dtype="float32")
        if vector.shape != (DIMENSION,):
            raise ValueError(f"{chunk_id} has vector shape {vector.shape}")
        vectors[str(chunk_id)] = vector
    return vectors


def run(args: argparse.Namespace) -> dict[str, Any]:
    import numpy
    import voyageai

    manifest = CorpusManifest.load(args.corpus)
    manifest.verify()
    screen_windows = load_windows(args.corpus)
    windows = [postgres_safe_window(window) for window in screen_windows]
    nul_normalized_windows = sum(
        screen.text != candidate.text
        for screen, candidate in zip(screen_windows, windows, strict=True)
    )
    historical = json.loads(args.historical.read_text(encoding="utf-8"))
    if historical["provenance"]["manifest_sha256"] != hashlib.sha256(
        (args.corpus / "manifest.json").read_bytes()
    ).hexdigest():
        raise ValueError("historical result and corpus manifest do not match")

    api_key = os.environ.get("RECALL_AML_API_KEY", "")
    dsn = os.environ.get("RECALL_AML_DATABASE_URL", "")
    table = os.environ.get("RECALL_AML_TABLE", "")
    if not api_key or not dsn or not table or not os.environ.get("VOYAGE_API_KEY"):
        raise SystemExit("hosted, database, and Voyage credentials are required")

    client = HostedClient(args.base_url, api_key)
    version = client.get("/version")
    if not (
        version.get("variant") == "C6_code4_exact_bm25"
        and version.get("exact_dense") is True
        and version.get("ordering_profile") == "source-session-c-collation-segment-v1"
        and version.get("window_renderer_profile") == "message-content-only-v1"
    ):
        raise ValueError("endpoint does not expose the frozen C6 parity contract")
    user_id = "code4-parity-" + uuid4().hex
    tenant = tenant_for(user_id)
    session_text = {
        rel: readable_text(resolve_corpus_path(args.corpus, rel))
        for rel in sorted(manifest.sessions)
    }
    add_latencies: list[float] = []
    try:
        def ingest(item: tuple[str, str]) -> float:
            rel, content = item
            result = client.call(
                "/v1/add",
                {
                    "request_id": "parity-" + hashlib.sha256(rel.encode()).hexdigest(),
                    "user_id": user_id,
                    "session_id": rel,
                    "messages": [{"role": "user", "content": content}],
                },
            )
            if not result.payload.get("success"):
                raise RuntimeError(f"Add failed for {rel}")
            return result.latency_ms

        with ThreadPoolExecutor(max_workers=args.add_workers) as pool:
            add_latencies.extend(pool.map(ingest, session_text.items()))

        persisted = load_persisted_vectors(dsn=dsn, table=table, tenant=tenant)
        if len(persisted) != len(windows):
            raise ValueError(
                f"hosted corpus has {len(persisted)} vectors, expected {len(windows)}"
            )

        chunk_ids: list[str] = []
        for rel in sorted(manifest.sessions):
            for segment, window in enumerate(item for item in windows if item.doc == rel):
                chunk_ids.append(expected_chunk_id(rel, segment, window.text))
        missing = [chunk_id for chunk_id in chunk_ids if chunk_id not in persisted]
        if missing:
            raise ValueError(f"hosted corpus is missing {len(missing)} expected chunk identities")

        matrix = numpy.vstack([persisted[chunk_id] for chunk_id in chunk_ids]).astype("float32")
        norms = numpy.linalg.norm(matrix, axis=1, keepdims=True)
        matrix /= numpy.where(norms == 0, 1, norms)
        lexical = BM25(windows)
        voyage = voyageai.Client()
        index_by_id = {chunk_id: index for index, chunk_id in enumerate(chunk_ids)}
        historical_by_task = {row["task_id"]: row for row in historical["per_task"]}

        rows: list[dict[str, Any]] = []
        search_latencies: list[float] = []
        dense_latencies: list[float] = []
        for task in sorted(discover_tasks(), key=lambda item: item.task_id):
            gold = {
                index
                for index, window in enumerate(windows)
                if window.doc.startswith(f"sessions/{task.task_id}/")
            }
            if not gold:
                continue
            query_vector = numpy.asarray(
                voyage.embed([task.prompt], model=MODEL, input_type="query").embeddings[0],
                dtype="float32",
            )
            query_vector /= numpy.linalg.norm(query_vector) or 1
            dense_started = time.perf_counter()
            dense_scores = matrix @ query_vector
            dense_latencies.append((time.perf_counter() - dense_started) * 1_000)
            lexical_ranking = rank_scores(lexical.scores(task.prompt), TOP_K)
            reference = fused_ranking(
                {index: float(score) for index, score in enumerate(dense_scores)},
                lexical_ranking,
                candidate_k=TOP_K,
                result_k=TOP_K,
            )
            hosted_result = client.call(
                "/v1/search",
                {"query": task.prompt, "user_id": user_id, "top_k": TOP_K},
            )
            search_latencies.append(hosted_result.latency_ms)
            hosted = [index_by_id[item["id"]] for item in hosted_result.payload["data"]]
            overlap = len(set(reference) & set(hosted))
            reference_rank = first_gold_rank(reference, gold)
            hosted_rank = first_gold_rank(hosted, gold)
            rows.append(
                {
                    "task_id": task.task_id,
                    "reference_rank": reference_rank,
                    "hosted_rank": hosted_rank,
                    "historical_treatment_rank": historical_by_task[task.task_id][
                        "treatment_rank"
                    ],
                    "top100_overlap": overlap,
                    "top100_jaccard": overlap / len(set(reference) | set(hosted)),
                    "ordered_top100_equal": reference == hosted,
                    "reference_recall_at_10": bool(reference_rank and reference_rank <= 10),
                    "hosted_recall_at_10": bool(hosted_rank and hosted_rank <= 10),
                    "reference_recall_at_100": reference_rank is not None,
                    "hosted_recall_at_100": hosted_rank is not None,
                    "search_ms": hosted_result.latency_ms,
                }
            )

        def mrr(field: str) -> float:
            return statistics.fmean(
                0.0 if row[field] is None else 1.0 / int(row[field]) for row in rows
            )

        return {
            "schema_version": 1,
            "experiment": "code4-hosted-exact-parity",
            "provenance": {
                "manifest_sha256": historical["provenance"]["manifest_sha256"],
                "historical_git_head": historical["provenance"]["git_head"],
                "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "candidate_commit": version.get("git_commit"),
                "candidate_generation": version.get("generation_id"),
                "corpus_sessions": len(manifest.sessions),
                "raw_windows": len(windows),
                "postgres_nul_normalized_windows": nul_normalized_windows,
            },
            "configuration": {
                "model": MODEL,
                "top_k": TOP_K,
                "add_workers": args.add_workers,
            },
            "metrics": {
                "queries": len(rows),
                "ordered_top100_equal": sum(row["ordered_top100_equal"] for row in rows),
                "mean_top100_overlap": statistics.fmean(row["top100_overlap"] for row in rows),
                "minimum_top100_overlap": min(row["top100_overlap"] for row in rows),
                "mean_top100_jaccard": statistics.fmean(row["top100_jaccard"] for row in rows),
                "reference_recall_at_10": statistics.fmean(
                    row["reference_recall_at_10"] for row in rows
                ),
                "hosted_recall_at_10": statistics.fmean(
                    row["hosted_recall_at_10"] for row in rows
                ),
                "reference_recall_at_100": statistics.fmean(
                    row["reference_recall_at_100"] for row in rows
                ),
                "hosted_recall_at_100": statistics.fmean(
                    row["hosted_recall_at_100"] for row in rows
                ),
                "reference_mrr": mrr("reference_rank"),
                "hosted_mrr": mrr("hosted_rank"),
                "historical_rank_matches": sum(
                    row["reference_rank"] == row["historical_treatment_rank"] for row in rows
                ),
                "add_p50_ms": statistics.median(add_latencies),
                "add_p95_ms": percentile(add_latencies, 0.95),
                "numpy_exact_dense_p50_ms": statistics.median(dense_latencies),
                "numpy_exact_dense_p95_ms": percentile(dense_latencies, 0.95),
                "hosted_search_p50_ms": statistics.median(search_latencies),
                "hosted_search_p95_ms": percentile(search_latencies, 0.95),
            },
            "passed": bool(
                len(rows) == 34
                and all(row["top100_overlap"] == TOP_K for row in rows)
                and all(row["reference_rank"] == row["hosted_rank"] for row in rows)
            ),
            "per_task": rows,
        }
    finally:
        try:
            client.call("/v1/delete", {"user_id": user_id})
        except (OSError, ValueError, RuntimeError) as error:
            print(f"warning: parity tenant cleanup failed: {error}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument(
        "--historical",
        type=Path,
        default=Path("results/retrieval/090-voyage-code4-direct-replacement.json"),
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--add-workers", type=int, default=3, choices=range(1, 4))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"passed": result["passed"], "metrics": result["metrics"]}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
