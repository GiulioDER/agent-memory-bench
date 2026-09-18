"""Deterministic retrieval replay for the preregistered RE-call Hosted variants."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
from pathlib import Path
from typing import Any, Protocol

from adapters.recall_hosted.adapter import HostedHttpClient, HostedHttpResponse, session_messages
from harness.adapters.base import CorpusManifest, resolve_corpus_path
from harness.tasks import TaskSpec, discover_tasks

ATTRIBUTION_VARIANTS = (
    "A0_raw",
    "A1_compiler",
    "A2_facets",
    "A3_rerank",
    "A4_pack_5000",
    "A4_pack_7000",
    "A4_pack_9000",
)
EXPERIENCE_VARIANTS = (
    "E0_raw",
    "E1_compiled",
    "E2_compiled_raw",
)
CODING_MATRIX_VARIANTS = (
    "C0_raw_lexical",
    "C1_splade",
    "C2_procedure",
    "C3_rerank",
    "C4_task_pack",
)
REGISTERED_VARIANTS = ATTRIBUTION_VARIANTS + EXPERIENCE_VARIANTS + CODING_MATRIX_VARIANTS

# Measured 2026-09-18 on VPS2: a valid idempotent Add needed all three compiler attempts and
# completed in 88 seconds.  The old 60 second transport timeout abandoned the response while the
# server continued and durably committed it.  Keep this above the observed retry envelope without
# changing the product's compiler timeout, retry policy, or deterministic fallback.
REPLAY_HTTP_TIMEOUT_SECONDS = 180.0

# Measured 2026-09-18 on VPS2: the CPU SPLADE sidecar had completed 576 of 2,284 chunks after
# 13 minutes, projecting to about 52 minutes.  This endpoint is an explicit corpus preparation
# operation, not Add or Search, so give only it a two-hour transport window.
SPARSE_BACKFILL_HTTP_TIMEOUT_SECONDS = 7_200.0


class Client(Protocol):
    def request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def request_with_headers(
        self, path: str, payload: dict[str, Any] | None = None
    ) -> HostedHttpResponse: ...


def build_replay_client(base_url: str, api_key: str) -> HostedHttpClient:
    """Construct the frozen replay transport with room for the product retry envelope."""
    return HostedHttpClient(base_url, api_key, timeout=REPLAY_HTTP_TIMEOUT_SECONDS)


def build_sparse_backfill_client(base_url: str, api_key: str) -> HostedHttpClient:
    """Construct the corpus-preparation transport without changing Add or Search timeouts."""
    return HostedHttpClient(
        base_url,
        api_key,
        timeout=SPARSE_BACKFILL_HTTP_TIMEOUT_SECONDS,
    )


def _digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request_id(namespace: str, relative: str, content_hash: str, offset: int) -> str:
    material = f"{namespace}\0{relative}\0{content_hash}\0{offset}"
    return hashlib.sha256(material.encode()).hexdigest()


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * quantile) - 1))
    return ordered[index]


def _complete_at(texts: list[str], terms: tuple[str, ...], limit: int) -> bool:
    joined = "\n".join(texts[:limit]).casefold()
    return bool(terms) and all(term in joined for term in terms)


def score_items(
    items: list[dict[str, Any]],
    fact_terms: tuple[str, ...],
    *,
    relevant_sources: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Score only after retrieval, using terms that are never sent to the memory system."""
    folded_terms = tuple(term.casefold() for term in fact_terms)
    texts = [str(item["content"]) for item in items]
    answer_bearing = [any(term in text.casefold() for term in folded_terms) for text in texts]
    first = next((index for index, hit in enumerate(answer_bearing, start=1) if hit), None)
    returned_sources = tuple(str(item["session_id"]) for item in items)
    unique_sources = set(returned_sources)
    expected_sources = set(relevant_sources)
    return {
        "hit_at_1": any(answer_bearing[:1]),
        "hit_at_5": any(answer_bearing[:5]),
        "hit_at_10": any(answer_bearing[:10]),
        "hit_at_100": any(answer_bearing[:100]),
        "hit_in_returned_budget": any(answer_bearing),
        "complete_coverage_at_5": _complete_at(texts, folded_terms, 5),
        "complete_coverage_at_10": _complete_at(texts, folded_terms, 10),
        "complete_coverage_at_100": _complete_at(texts, folded_terms, 100),
        "complete_coverage": _complete_at(texts, folded_terms, len(texts)),
        "reciprocal_rank": 0.0 if first is None else 1.0 / first,
        "source_session_recall": (
            None
            if not expected_sources
            else len(unique_sources & expected_sources) / len(expected_sources)
        ),
        "duplicate_session_concentration": (
            0.0 if not returned_sources else 1.0 - len(unique_sources) / len(returned_sources)
        ),
        "item_count": len(items),
        "character_count": sum(len(text) for text in texts),
    }


def _validated_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = response.get("data")
    if not isinstance(data, list):
        raise TypeError("hosted Search response has no data array")
    items: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise TypeError("hosted Search item has no string id")
        if not isinstance(item.get("content"), str):
            raise TypeError("hosted Search item has no string content")
        if not isinstance(item.get("session_id"), str) or not item["session_id"]:
            raise TypeError("hosted Search item has no string session_id")
        items.append(item)
    return items


def _relevant_sources(
    corpus: CorpusManifest, fact_terms: tuple[str, ...]
) -> tuple[str, ...]:
    """Resolve labeled source sessions only after Search for diagnostic scoring."""
    folded_terms = tuple(term.casefold() for term in fact_terms)
    relevant: list[str] = []
    for relative in sorted(corpus.sessions):
        messages = session_messages(resolve_corpus_path(corpus.root, relative))
        text = "\n".join(str(message["content"]) for message in messages).casefold()
        if any(term in text for term in folded_terms):
            relevant.append(relative)
    return tuple(relevant)


def _fallback_header(headers: dict[str, str], name: str) -> bool:
    value = headers.get(name)
    if value not in {"0", "1"}:
        raise RuntimeError(f"hosted Search response has invalid or missing fallback telemetry: {name}")
    return value == "1"


def _task_type_header(headers: dict[str, str]) -> str:
    value = headers.get("x-recall-task-type")
    if value not in {"feature", "bugfix", "unknown"}:
        raise RuntimeError("hosted Search response has invalid or missing task routing telemetry")
    return value


def run_replay(
    client: Client,
    *,
    variant_name: str,
    corpus: CorpusManifest,
    tasks: list[TaskSpec],
    namespace: str,
    reuse_corpus: bool = False,
    sparse_backfill_client: Client | None = None,
    resume_ingest: bool = False,
) -> dict[str, Any]:
    if variant_name not in REGISTERED_VARIANTS:
        raise ValueError(f"unregistered hosted variant {variant_name!r}")
    corpus.verify()
    version = client.request("/version")
    if version.get("variant") != variant_name:
        raise RuntimeError(
            f"hosted variant mismatch: expected {variant_name}, got {version.get('variant')!r}"
        )
    if reuse_corpus and resume_ingest:
        raise ValueError("resume ingest cannot be combined with corpus reuse")
    if resume_ingest and variant_name != "C2_procedure":
        raise ValueError("resume ingest is registered only for the amended C2 procedure run")
    if not reuse_corpus and not resume_ingest:
        client.request("/v1/delete", {"user_id": namespace})
    if reuse_corpus and variant_name != "C1_splade" and variant_name not in {
        "C3_rerank",
        "C4_task_pack",
    }:
        raise ValueError(f"{variant_name} is not a registered corpus-reuse arm")

    if reuse_corpus:
        preparation_client = sparse_backfill_client or client
        prepared = preparation_client.request(
            "/v1/sparse/backfill", {"user_id": namespace}
        )
        sparse_count = prepared.get("sparse_chunk_count")
        if (
            prepared.get("status") != "ready"
            or isinstance(sparse_count, bool)
            or not isinstance(sparse_count, int)
            or sparse_count <= 0
        ):
            raise RuntimeError("hosted sparse backfill did not prove corpus readiness")

    add_latencies: list[float] = []
    compiler_fallbacks = 0
    messages_offered = 0
    for relative, content_hash in sorted(corpus.sessions.items()):
        messages = session_messages(resolve_corpus_path(corpus.root, relative))
        for offset in range(0, len(messages), 256):
            batch = messages[offset : offset + 256]
            request_id = _request_id(namespace, relative, content_hash, offset)
            payload = {
                "request_id": request_id,
                "messages": batch,
                "user_id": namespace,
                "session_id": relative,
            }
            if not reuse_corpus:
                started = time.perf_counter()
                response = client.request("/v1/add", payload)
                add_latencies.append((time.perf_counter() - started) * 1_000)
                expected = {
                    "success": True,
                    "request_id": request_id,
                    "user_id": namespace,
                    "session_id": relative,
                }
                if not expected.items() <= response.items():
                    raise RuntimeError("hosted Add response did not echo the request identity")
                compiler_fallbacks += int(response.get("compiler_fallback") is True)
            messages_offered += len(batch)

    search_latencies: list[float] = []
    facet_fallbacks = 0
    reranker_fallbacks = 0
    rows: list[dict[str, Any]] = []
    for task in sorted(tasks, key=lambda item: item.task_id):
        payload = {"query": task.prompt, "user_id": namespace, "top_k": 100}
        started = time.perf_counter()
        http_response = client.request_with_headers("/v1/search", payload)
        response = http_response.payload
        latency_ms = (time.perf_counter() - started) * 1_000
        search_latencies.append(latency_ms)
        facet_fallback = _fallback_header(
            http_response.headers, "x-recall-facet-fallback"
        )
        reranker_fallback = _fallback_header(
            http_response.headers, "x-recall-reranker-fallback"
        )
        task_type = _task_type_header(http_response.headers)
        facet_fallbacks += int(facet_fallback)
        reranker_fallbacks += int(reranker_fallback)
        items = _validated_items(response)
        rows.append(
            {
                "task_id": task.task_id,
                "kind": task.kind,
                "query_sha256": hashlib.sha256(task.prompt.encode()).hexdigest(),
                "fact_terms_sha256": hashlib.sha256(
                    json.dumps(task.fact_terms, separators=(",", ":")).encode()
                ).hexdigest(),
                "latency_ms": latency_ms,
                "facet_fallback": facet_fallback,
                "reranker_fallback": reranker_fallback,
                "task_type": task_type,
                "metrics": score_items(
                    items,
                    task.fact_terms,
                    relevant_sources=_relevant_sources(corpus, task.fact_terms),
                ),
                "items": items,
            }
        )

    def mean(metric: str) -> float:
        return statistics.fmean(float(row["metrics"][metric]) for row in rows)

    def optional_mean(metric: str) -> float | None:
        values = [row["metrics"][metric] for row in rows]
        present = [float(value) for value in values if value is not None]
        return statistics.fmean(present) if present else None

    routing_aggregate: dict[str, dict[str, Any]] = {}
    for task_type in ("feature", "bugfix", "unknown"):
        routed = [row for row in rows if row["task_type"] == task_type]
        if not routed:
            continue
        routing_aggregate[task_type] = {
            "task_count": len(routed),
            "complete_coverage_at_10": statistics.fmean(
                float(row["metrics"]["complete_coverage_at_10"]) for row in routed
            ),
            "mean_reciprocal_rank": statistics.fmean(
                float(row["metrics"]["reciprocal_rank"]) for row in routed
            ),
            "mean_character_count": statistics.fmean(
                float(row["metrics"]["character_count"]) for row in routed
            ),
        }

    task_digest = hashlib.sha256(
        "".join(
            f"{task.task_id}\0{_digest_file(task.path / 'task.json')}\n" for task in tasks
        ).encode()
    ).hexdigest()
    return {
        "schema_version": 1,
        "variant": variant_name,
        "namespace": namespace,
        "version": version,
        "corpus_manifest_sha256": _digest_file(corpus.root / "manifest.json"),
        "task_set_sha256": task_digest,
        "sessions_offered": len(corpus.sessions),
        "messages_offered": messages_offered,
        "task_count": len(rows),
        "http_timeout_seconds": REPLAY_HTTP_TIMEOUT_SECONDS,
        "sparse_backfill_timeout_seconds": (
            SPARSE_BACKFILL_HTTP_TIMEOUT_SECONDS if reuse_corpus else None
        ),
        "corpus_reused": reuse_corpus,
        "dense_embedding_pass": not reuse_corpus,
        "ingest_resumed": resume_ingest,
        "routing_aggregate": routing_aggregate,
        "aggregate": {
            "hit_at_1": mean("hit_at_1"),
            "hit_at_5": mean("hit_at_5"),
            "hit_at_10": mean("hit_at_10"),
            "hit_at_100": mean("hit_at_100"),
            "hit_in_returned_budget": mean("hit_in_returned_budget"),
            "complete_coverage_at_5": mean("complete_coverage_at_5"),
            "complete_coverage_at_10": mean("complete_coverage_at_10"),
            "complete_coverage_at_100": mean("complete_coverage_at_100"),
            "complete_coverage": mean("complete_coverage"),
            "mean_reciprocal_rank": mean("reciprocal_rank"),
            "mean_source_session_recall": optional_mean("source_session_recall"),
            "mean_duplicate_session_concentration": mean(
                "duplicate_session_concentration"
            ),
            "mean_item_count": mean("item_count"),
            "mean_character_count": mean("character_count"),
            "add_p50_ms": _percentile(add_latencies, 0.50),
            "add_p95_ms": _percentile(add_latencies, 0.95),
            "search_p50_ms": _percentile(search_latencies, 0.50),
            "search_p95_ms": _percentile(search_latencies, 0.95),
            "compiler_fallbacks": compiler_fallbacks,
            "facet_fallbacks": facet_fallbacks,
            "reranker_fallbacks": reranker_fallbacks,
            "sparse_failures": 0,
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=REGISTERED_VARIANTS, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--tasks", type=Path, default=Path("tasks"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--namespace")
    parser.add_argument("--reuse-corpus", action="store_true")
    parser.add_argument("--resume-ingest", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite replay artifact: {args.output}")
    api_key = os.environ.get("AMB_RECALL_HOSTED_API_KEY", "")
    if not api_key:
        raise SystemExit("AMB_RECALL_HOSTED_API_KEY is required")
    namespace = args.namespace or f"aml-replay-{args.variant.casefold().replace('_', '-')}"
    result = run_replay(
        build_replay_client(args.base_url, api_key),
        variant_name=args.variant,
        corpus=CorpusManifest.load(args.corpus),
        tasks=discover_tasks(args.tasks),
        namespace=namespace,
        reuse_corpus=args.reuse_corpus,
        sparse_backfill_client=(
            build_sparse_backfill_client(args.base_url, api_key)
            if args.reuse_corpus
            else None
        ),
        resume_ingest=args.resume_ingest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
