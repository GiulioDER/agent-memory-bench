"""Harness side retrieval, using the same published RE call search command as recall."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from adapters.recall.adapter import RecallAdapter
from harness.adapters.base import (
    ArmSpec,
    CorpusManifest,
    IngestReport,
    MemoryAdapter,
    namespace_path,
)
from harness.gate import AdmissionSignal
from harness.memory_bundles import MemoryItem
from harness.memory_prompt import estimated_input_tokens, format_memory_items, sha256_text


class PrefetchError(RuntimeError):
    pass


def _last_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    candidates: list[tuple[int, dict[str, Any]]] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, consumed = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            candidates.append((consumed, value))
    if not candidates:
        raise PrefetchError("recall search returned no JSON object")
    return max(candidates, key=lambda item: item[0])[1]


def parse_prefetch_output(stdout: str) -> tuple[tuple[MemoryItem, ...], dict[str, Any]]:
    data = _last_json_object(stdout)
    bundle = data.get("bundle") if isinstance(data.get("bundle"), dict) else {}
    raw_items = data.get("evidence", data.get("hits", data.get("results", bundle.get("items", []))))
    if raw_items is None:
        raw_items = []
    if not isinstance(raw_items, list):
        raise PrefetchError("recall search evidence is not a list")
    items: list[MemoryItem] = []
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            raise PrefetchError(f"recall search evidence item {index} is not an object")
        text = raw.get("evidence_text", raw.get("text", raw.get("content", "")))
        if not text:
            continue
        items.append(
            MemoryItem(
                memory_id=str(raw.get("memory_id", raw.get("id", f"prefetch_{index:04d}"))),
                source_path=str(raw.get("source_path", raw.get("source", "recall"))),
                source_sha256=str(raw.get("source_sha256", "unknown")),
                evidence_text=str(text),
                recorded_at=str(raw.get("recorded_at", raw.get("indexed_at", "unknown"))),
                validity=str(raw.get("validity", "current" if raw.get("valid_until") is None else "superseded")),
                supersedes=raw.get("supersedes"),
            )
        )
    items.sort(key=lambda item: item.memory_id)
    abstained = bool(
        data.get(
            "abstained",
            data.get("status") == "abstained" or bundle.get("decision") == "abstain",
        )
    )
    return tuple(items), {"abstained": abstained, "hit_count": len(items), "raw": data}


def run_prefetch(
    adapter: RecallAdapter,
    namespace: str,
    query: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[tuple[MemoryItem, ...], dict[str, Any]]:
    command = [
        sys.executable,
        "-m",
        "recall.cli",
        "--tenant",
        namespace,
        "search",
        "-k",
        str(adapter.prefetch_k),
        "--evidence",
        query,
    ]
    started = time.monotonic()
    try:
        result = runner(
            command,
            env={**adapter.search_env(namespace), "PYTHONPATH": adapter.search_env(namespace).get("PYTHONPATH", "")},
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise PrefetchError("recall prefetch timed out") from error
    elapsed_ms = (time.monotonic() - started) * 1000.0
    if result.returncode != 0:
        raise PrefetchError(f"recall prefetch failed with exit {result.returncode}: {result.stderr[-1000:]}")
    items, parsed = parse_prefetch_output(result.stdout)
    parsed["prefetch_wall_time_ms"] = elapsed_ms
    parsed["query_sha256"] = sha256_text(query)
    parsed["result_sha256"] = sha256_text(result.stdout)
    return items, parsed


class RecallPrefetchAdapter(MemoryAdapter):
    name = "recall_prefetch"

    def __init__(
        self,
        recall: RecallAdapter,
        staging_root: str | Path,
        base_prompt_file: str | Path,
        *,
        prefetch_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.recall = recall
        self.staging_root = Path(staging_root)
        self.base_prompt_file = Path(base_prompt_file)
        self.prefetch_runner = prefetch_runner

    def ingest(self, corpus: CorpusManifest, namespace: str) -> IngestReport:
        report = self.recall.ingest(corpus, namespace)
        return IngestReport(
            arm=self.name,
            namespace=report.namespace,
            sessions_offered=report.sessions_offered,
            items_stored=report.items_stored,
            wall_time_ms=report.wall_time_ms,
            notes=report.notes + ("retrieval is performed by the harness before each session",),
        )

    def build(self, session_dir: Path, namespace: str) -> ArmSpec:
        raise TypeError("recall_prefetch requires build_for_task so the exact task prompt is queried")

    def build_for_task(self, session_dir: Path, namespace: str, task_id: str, user_input: str) -> ArmSpec:
        items, result = run_prefetch(
            self.recall, namespace, user_input, runner=self.prefetch_runner
        )
        memory_text = format_memory_items(items)
        # Validated at the join. Found by `tests/test_namespace_guard.py` on the day it
        # was written, which is the point of it: neither the audit nor the architect
        # review named this site, and both of them looked.
        prompt = namespace_path(self.staging_root, namespace, task_id, "prefetch.system.md")
        prompt.parent.mkdir(parents=True, exist_ok=True)
        static = self.base_prompt_file.read_text(encoding="utf-8").rstrip()
        prompt.write_text(memory_text.rstrip() + "\n\n" + static + "\n", encoding="utf-8")
        payload = prompt.with_name("prefetch.payload.json")
        payload.write_text(
            json.dumps(
                {
                    "query": user_input,
                    "query_sha256": result["query_sha256"],
                    "result": result["raw"],
                    "result_sha256": result["result_sha256"],
                    "injected_text_sha256": sha256_text(memory_text),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        diagnostic = {
            "kind": self.name,
            "task_id": task_id,
            "query_sha256": result["query_sha256"],
            "query_text": None,
            "result_sha256": result["result_sha256"],
            "hit_count": result["hit_count"],
            "abstained": result["abstained"],
            "prefetch_wall_time_ms": result["prefetch_wall_time_ms"],
            "prefetch_input_tokens": None,
            "prefetch_status": "ok",
            "config_identity": hashlib.sha256(
                json.dumps(self.recall.config, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "injected_text_sha256": sha256_text(memory_text),
            "injected_input_tokens": estimated_input_tokens(memory_text),
        }
        prompt_hash = hashlib.sha256(prompt.read_bytes()).hexdigest()
        return ArmSpec(
            arm=self.name,
            bare=True,
            append_system_prompt_file=prompt,
            metadata={"memory": "prefetched", "prompt_sha256": prompt_hash, "memory_diagnostic": diagnostic},
        )

    def admission_signal(self) -> AdmissionSignal:
        return AdmissionSignal(arm=self.name, metadata={"diagnostic_kind": self.name})

    def describe(self) -> dict:
        return {
            "arm": self.name,
            "memory": "harness prefetch",
            "recall_config_sha256": hashlib.sha256(
                json.dumps(self.recall.config, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        }
