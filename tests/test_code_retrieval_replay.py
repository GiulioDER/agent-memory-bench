from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from adapters.code_retrieval_replay import adapter as replay
from scripts.retrieval_probe import Window


def _artifact(corpus: Path, *, passed: bool = True) -> dict:
    manifest_sha = hashlib.sha256((corpus / "manifest.json").read_bytes()).hexdigest()
    hits = [
        {
            "rank": rank,
            "index": 10 - rank,
            "source_path": f"sessions/task-a/source-{10 - rank}.jsonl",
            "text_sha256": hashlib.sha256(f"window {10 - rank}".encode()).hexdigest(),
        }
        for rank in range(1, 11)
    ]
    return {
        "schema_version": 1,
        "experiment": "091-voyage-code4-task-solve-evidence",
        "provenance": {"manifest_sha256": manifest_sha, "raw_windows": 10},
        "configuration": {
            "control_model": "voyage-code-3",
            "treatment_model": "voyage-code-4",
            "candidate_k_per_leg": 100,
            "result_k": 100,
            "evidence_k": 10,
            "rrf_k": 60,
            "window_words": 160,
            "window_stride": 120,
        },
        "evidence_gate": {"passed": passed},
        "tasks": [
            {
                "task_id": "task-a",
                "query_sha256": hashlib.sha256(b"fix it").hexdigest(),
                "code3_replay": {"model": "voyage-code-3", "windows": hits},
                "code4_replay": {"model": "voyage-code-4", "windows": hits},
            }
        ],
    }


@pytest.fixture
def replay_files(tmp_path: Path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "manifest.json").write_text("{}\n", encoding="utf-8")
    windows = [
        Window(doc=f"sessions/task-a/source-{index}.jsonl", text=f"window {index}")
        for index in range(10)
    ]
    monkeypatch.setattr(replay, "load_windows", lambda root: windows)
    artifact = tmp_path / "evidence.json"
    artifact.write_text(json.dumps(_artifact(corpus)), encoding="utf-8")
    return corpus, artifact


def test_catalog_validates_and_replay_preserves_rank_order(replay_files, tmp_path: Path) -> None:
    corpus, artifact = replay_files
    catalog = replay.CodeRetrievalReplayCatalog.load(
        artifact, corpus, expected_task_ids={"task-a"}
    )
    static = tmp_path / "static.md"
    static.write_text("repository rules\n", encoding="utf-8")
    adapter = replay.CodeRetrievalReplayAdapter(
        "code4_replay", catalog, tmp_path / "staging", static
    )

    spec = adapter.build_for_task(tmp_path / "unused", "safe-namespace", "task-a", "fix it")
    prompt = Path(spec.append_system_prompt_file).read_text(encoding="utf-8")

    assert prompt.index("window 9") < prompt.index("window 8")
    assert prompt.rstrip().endswith("repository rules")
    diagnostic = spec.metadata["memory_diagnostic"]
    assert diagnostic["window_indices"] == list(range(9, -1, -1))
    assert diagnostic["model"] == "voyage-code-4"


def test_catalog_refuses_failed_evidence_gate(replay_files) -> None:
    corpus, artifact = replay_files
    artifact.write_text(json.dumps(_artifact(corpus, passed=False)), encoding="utf-8")

    with pytest.raises(ValueError, match="did not pass"):
        replay.CodeRetrievalReplayCatalog.load(artifact, corpus)


def test_catalog_refuses_window_hash_drift(replay_files) -> None:
    corpus, artifact = replay_files
    data = json.loads(artifact.read_text(encoding="utf-8"))
    data["tasks"][0]["code3_replay"]["windows"][0]["text_sha256"] = "0" * 64
    artifact.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="text hash mismatch"):
        replay.CodeRetrievalReplayCatalog.load(artifact, corpus)


def test_adapter_refuses_prompt_drift(replay_files, tmp_path: Path) -> None:
    corpus, artifact = replay_files
    catalog = replay.CodeRetrievalReplayCatalog.load(artifact, corpus)
    static = tmp_path / "static.md"
    static.write_text("repository rules\n", encoding="utf-8")
    adapter = replay.CodeRetrievalReplayAdapter(
        "code3_replay", catalog, tmp_path / "staging", static
    )

    with pytest.raises(ValueError, match="prompt hash"):
        adapter.build_for_task(tmp_path / "unused", "safe-namespace", "task-a", "changed")
