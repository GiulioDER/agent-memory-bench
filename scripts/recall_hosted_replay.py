"""Deterministic retrieval replay for the preregistered RE-call Hosted variants."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any, Protocol

from adapters.recall_hosted.adapter import HostedHttpClient, session_messages
from harness.adapters.base import CorpusManifest, resolve_corpus_path
from harness.tasks import TaskSpec, discover_tasks

REGISTERED_VARIANTS = (
    "A0_raw",
    "A1_compiler",
    "A2_facets",
    "A3_rerank",
    "A4_pack_5000",
    "A4_pack_7000",
    "A4_pack_9000",
)


class Client(Protocol):
    def request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]: ...


def _digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request_id(namespace: str, relative: str, content_hash: str, offset: int) -> str:
    material = f"{namespace}\0{relative}\0{content_hash}\0{offset}"
    return hashlib.sha256(material.encode()).hexdigest()


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * quantile)))
    return ordered[index]


def score_items(items: list[dict[str, Any]], fact_terms: tuple[str, ...]) -> dict[str, Any]:
    """Score only after retrieval, using terms that are never sent to the memory system."""
    folded_terms = tuple(term.casefold() for term in fact_terms)
    texts = [str(item["content"]) for item in items]
    answer_bearing = [any(term in text.casefold() for term in folded_terms) for text in texts]
    first = next((index for index, hit in enumerate(answer_bearing, start=1) if hit), None)
    joined = "\n".join(texts).casefold()
    return {
        "hit_at_1": any(answer_bearing[:1]),
        "hit_at_5": any(answer_bearing[:5]),
        "hit_at_10": any(answer_bearing[:10]),
        "hit_in_returned_budget": any(answer_bearing),
        "complete_coverage": bool(folded_terms) and all(term in joined for term in folded_terms),
        "reciprocal_rank": 0.0 if first is None else 1.0 / first,
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
        items.append(item)
    return items


def run_replay(
    client: Client,
    *,
    variant_name: str,
    corpus: CorpusManifest,
    tasks: list[TaskSpec],
    namespace: str,
) -> dict[str, Any]:
    if variant_name not in REGISTERED_VARIANTS:
        raise ValueError(f"unregistered hosted variant {variant_name!r}")
    corpus.verify()
    version = client.request("/version")
    if version.get("variant") != variant_name:
        raise RuntimeError(
            f"hosted variant mismatch: expected {variant_name}, got {version.get('variant')!r}"
        )
    client.request("/v1/delete", {"user_id": namespace})

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
    rows: list[dict[str, Any]] = []
    for task in sorted(tasks, key=lambda item: item.task_id):
        payload = {"query": task.prompt, "user_id": namespace, "top_k": 100}
        started = time.perf_counter()
        response = client.request("/v1/search", payload)
        latency_ms = (time.perf_counter() - started) * 1_000
        search_latencies.append(latency_ms)
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
                "metrics": score_items(items, task.fact_terms),
                "items": items,
            }
        )

    def mean(metric: str) -> float:
        return statistics.fmean(float(row["metrics"][metric]) for row in rows)

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
        "aggregate": {
            "hit_at_1": mean("hit_at_1"),
            "hit_at_5": mean("hit_at_5"),
            "hit_at_10": mean("hit_at_10"),
            "hit_in_returned_budget": mean("hit_in_returned_budget"),
            "complete_coverage": mean("complete_coverage"),
            "mean_reciprocal_rank": mean("reciprocal_rank"),
            "mean_item_count": mean("item_count"),
            "mean_character_count": mean("character_count"),
            "add_p50_ms": _percentile(add_latencies, 0.50),
            "add_p95_ms": _percentile(add_latencies, 0.95),
            "search_p50_ms": _percentile(search_latencies, 0.50),
            "search_p95_ms": _percentile(search_latencies, 0.95),
            "compiler_fallbacks": compiler_fallbacks,
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
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite replay artifact: {args.output}")
    api_key = os.environ.get("AMB_RECALL_HOSTED_API_KEY", "")
    if not api_key:
        raise SystemExit("AMB_RECALL_HOSTED_API_KEY is required")
    namespace = args.namespace or f"aml-replay-{args.variant.casefold().replace('_', '-')}"
    result = run_replay(
        HostedHttpClient(args.base_url, api_key, timeout=60),
        variant_name=args.variant,
        corpus=CorpusManifest.load(args.corpus),
        tasks=discover_tasks(args.tasks),
        namespace=namespace,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
