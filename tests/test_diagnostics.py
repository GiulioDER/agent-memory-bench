import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from adapters.recall.adapter import RecallAdapter
from adapters.recall_prefetch.adapter import (
    PrefetchError,
    parse_prefetch_output,
    run_prefetch,
)
from harness.adapters.base import CorpusManifest, MemoryAdapter
from harness.gate import AdmissionSignal, check_session
from harness.memory_bundles import MemoryBundleCatalog
from harness.memory_prompt import format_memory_items
from harness.schema import SessionRecord
from harness.tasks import TaskSpec


def fixture_catalog(tmp_path: Path, *, evidence: str = "The timestamps are UTC."):
    source = tmp_path / "sessions" / "demo" / "p01.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"role": "user", "content": evidence}) + "\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    corpus = CorpusManifest(root=tmp_path, sessions={"sessions/demo/p01.jsonl": digest})
    task = TaskSpec("demo", "do the task", "primary", (), tmp_path, "bundle_demo")
    bundles = tmp_path / "oracle"
    bundles.mkdir()
    (bundles / "bundles.jsonl").write_text(
        json.dumps(
            {
                "bundle_id": "bundle_demo",
                "task_id": "demo",
                "items": [
                    {
                        "memory_id": "mem_demo",
                        "source_path": "sessions/demo/p01.jsonl",
                        "source_sha256": digest,
                        "evidence_text": evidence,
                        "recorded_at": "2026-08-25",
                        "validity": "current",
                        "supersedes": None,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return corpus, task, MemoryBundleCatalog.load(bundles, corpus, [task])


def test_valid_bundle_and_deterministic_prompt(tmp_path):
    corpus, task, catalog = fixture_catalog(tmp_path)
    assert catalog.get_for_task(task).items[0].memory_id == "mem_demo"
    item = catalog.get_for_task(task).items[0]
    assert format_memory_items([item]) == format_memory_items([item])
    assert catalog.digest == MemoryBundleCatalog.load(catalog.root, corpus, [task]).digest


def test_bundle_rejects_hash_and_missing_excerpt(tmp_path):
    corpus, task, catalog = fixture_catalog(tmp_path)
    manifest = catalog.root / "bundles.jsonl"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["items"][0]["source_sha256"] = "0" * 64
    manifest.write_text(json.dumps(data) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source hash mismatch"):
        MemoryBundleCatalog.load(catalog.root, corpus, [task])


def test_controls_are_explicitly_empty(tmp_path):
    _corpus, _, catalog = fixture_catalog(tmp_path)
    control = TaskSpec("control", "control", "control", (), tmp_path, None)
    assert catalog.get_for_task(control) is None


def test_prefetch_parser_and_exact_query(monkeypatch, tmp_path):
    monkeypatch.setenv("RECALL_DSN", "postgresql://example/recall")
    recall = RecallAdapter(tmp_path, tmp_path / "base.md")
    (tmp_path / "base.md").write_text("base", encoding="utf-8")
    seen = {}

    def fake_runner(command, **kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "bundle": {
                        "decision": "answer",
                        "items": [
                            {"chunk_id": "c1", "text": "fact", "source": "session"}
                        ],
                    }
                }
            ),
            "",
        )

    items, result = run_prefetch(recall, "tenant", "exact task prompt", runner=fake_runner)
    assert seen["command"][-1] == "exact task prompt"
    assert items[0].evidence_text == "fact"
    assert result["abstained"] is False
    with pytest.raises(PrefetchError):
        parse_prefetch_output("not json")


def test_existing_adapters_keep_build_for_task_contract():
    class Adapter(MemoryAdapter):
        name = "fixture"

        def build(self, session_dir, namespace):
            from harness.adapters.base import ArmSpec

            return ArmSpec(self.name)

        def ingest(self, corpus, namespace):
            from harness.adapters.base import IngestReport

            return IngestReport(self.name, namespace, 0)

        def admission_signal(self):
            return AdmissionSignal(self.name)

    assert Adapter().build_for_task(Path("."), "n", "task", "prompt").arm == "fixture"


def test_oracle_digest_mismatch_is_not_admitted():
    record = SessionRecord(
        task_id="demo",
        arm="oracle_memory",
        success=True,
        metadata={
            "memory_diagnostic": {
                "kind": "oracle_memory",
                "task_id": "demo",
                "bundle_id": "bundle_demo",
                "bundle_sha256": "wrong",
                "catalog_sha256": "catalog",
                "injected_text_sha256": "text",
                "status": "ok",
            }
        },
    )
    signal = AdmissionSignal(
        arm="oracle_memory",
        metadata={
            "diagnostic_kind": "oracle_memory",
            "catalog_sha256": "catalog",
            "bundle_digests": {"demo": "right"},
        },
    )
    verdict = check_session(record, signal)
    assert not verdict.admitted
    assert any("bundle digest mismatch" in reason for reason in verdict.reasons)


def test_prefetch_abstention_is_behavioral_not_wiring_failure():
    record = SessionRecord(
        task_id="demo",
        arm="recall_prefetch",
        success=False,
        metadata={
            "memory_diagnostic": {
                "kind": "recall_prefetch",
                "query_sha256": "q",
                "result_sha256": "r",
                "prefetch_status": "ok",
                "abstained": True,
            }
        },
    )
    verdict = check_session(record, AdmissionSignal(arm="recall_prefetch", metadata={"diagnostic_kind": "recall_prefetch"}))
    assert verdict.admitted
