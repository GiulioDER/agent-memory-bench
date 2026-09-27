"""TS-1's served-evidence arms replay a memory system's own top items like 091's windows.

Invariants: ``c9_raw`` shows each item's content exactly as served, ``c9_norm`` the same content
through ``harness.plants.normalise`` (the transform 091's windows went through), both in rank
order in 091's wrapper, a non-raw item's kind named in its Source line; the served artifact is
refused when a task has fewer than 10 items or the roster differs; a served arm cannot be built
without it; the three TS-1 arms count as instruction-matched, one served arm beside a live arm
does not.

Red proof, 2026-09-27, each against the named production line with this file unchanged
(``PYTHONDONTWRITEBYTECODE=1``):
- ``format_served_evidence`` normalising always (``if True``):
  ``test_raw_arm_shows_content_as_served_and_norm_arm_normalised`` fails at the raw ``in``.
- the Source line ignoring the kind:
  ``test_a_non_raw_item_names_its_kind`` fails at ``[compiled]``.
- ``load_served`` without the fewer-than-10 check:
  ``test_served_evidence_with_too_few_items_is_refused`` fails at ``DID NOT RAISE``.
- ``load_served`` without the roster check:
  ``test_served_roster_must_match_the_tasks`` fails at ``DID NOT RAISE``.
- ``CodeRetrievalReplayAdapter`` without the served-artifact check:
  ``test_a_served_arm_needs_a_served_artifact`` fails at ``DID NOT RAISE``.
- ``instruction_arms_are_matched`` back to set equality with every replay arm:
  ``test_ts1_arms_are_instruction_matched`` fails at its first assertion.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from adapters.code_retrieval_replay import adapter as replay
from adapters.code_retrieval_replay.served import load_served
from scripts.retrieval_probe import Window

HEADER = "[2026-09-26 10:00 UTC] "


def _artifact(corpus: Path) -> dict:
    """A minimal 091 artifact (as ``tests/test_code_retrieval_replay.py`` builds it)."""
    hits = [{"rank": rank, "index": 10 - rank, "source_path": f"sessions/task-a/source-{10 - rank}.jsonl",
             "text_sha256": hashlib.sha256(f"window {10 - rank}".encode()).hexdigest()} for rank in range(1, 11)]
    return {
        "schema_version": 1,
        "experiment": "091-voyage-code4-task-solve-evidence",
        "provenance": {"manifest_sha256": hashlib.sha256((corpus / "manifest.json").read_bytes()).hexdigest(),
                       "raw_windows": 10},
        "configuration": {"control_model": "voyage-code-3", "treatment_model": "voyage-code-4",
                          "candidate_k_per_leg": 100, "result_k": 100, "evidence_k": 10, "rrf_k": 60,
                          "window_words": 160, "window_stride": 120},
        "evidence_gate": {"passed": True},
        "tasks": [{"task_id": "task-a", "query_sha256": hashlib.sha256(b"fix it").hexdigest(),
                   "code3_replay": {"model": "voyage-code-3", "windows": hits},
                   "code4_replay": {"model": "voyage-code-4", "windows": hits}}],
    }


def _served(task_ids=("task-a",), items: int = 10, kinds=None) -> dict:
    kinds = kinds or ["raw"] * items
    return {"rows": [{"task_id": task_id, "status": 200, "top_items": [
        {"id": f"i{rank}", "kind": kinds[rank], "session_id": f"sessions/task-a/p{rank}.jsonl",
         "created_at": "2026-09-26T10:00:00Z", "content": f"{HEADER}Keep APP_MAX_RETRIES at {rank}"}
        for rank in range(items)]} for task_id in task_ids]}


def _write(path: Path, payload: dict) -> Path:
    path.write_bytes(gzip.compress(json.dumps(payload).encode()))
    return path


@pytest.fixture
def catalog_files(tmp_path: Path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "manifest.json").write_text("{}\n", encoding="utf-8")
    windows = [Window(doc=f"sessions/task-a/source-{i}.jsonl", text=f"window {i}") for i in range(10)]
    monkeypatch.setattr(replay, "load_windows", lambda root: windows)
    artifact = tmp_path / "evidence.json"
    artifact.write_text(json.dumps(_artifact(corpus)), encoding="utf-8")
    static = tmp_path / "static.md"
    static.write_text("repository rules\n", encoding="utf-8")
    return corpus, artifact, static


def _prompt(catalog, arm: str, tmp_path: Path, static: Path) -> str:
    adapter = replay.CodeRetrievalReplayAdapter(arm, catalog, tmp_path / "staging", static)
    spec = adapter.build_for_task(tmp_path / "unused", "ns", "task-a", "fix it")
    return Path(spec.append_system_prompt_file).read_text(encoding="utf-8")


def test_raw_arm_shows_content_as_served_and_norm_arm_normalised(catalog_files, tmp_path: Path) -> None:
    corpus, artifact, static = catalog_files
    served = _write(tmp_path / "served.json.gz", _served())
    catalog = replay.CodeRetrievalReplayCatalog.load(artifact, corpus, served_path=served)

    raw = _prompt(catalog, "c9_raw", tmp_path, static)
    norm = _prompt(catalog, "c9_norm", tmp_path, static)

    assert "Keep APP_MAX_RETRIES at 0" in raw
    assert raw.index("rank 1]") < raw.index("rank 2]") and raw.rstrip().endswith("repository rules")
    assert "APP_MAX_RETRIES" not in norm and "appmaxretries at 0" in norm


def test_a_non_raw_item_names_its_kind(catalog_files, tmp_path: Path) -> None:
    corpus, artifact, static = catalog_files
    served = _write(tmp_path / "served.json.gz", _served(kinds=["compiled"] + ["raw"] * 9))
    catalog = replay.CodeRetrievalReplayCatalog.load(artifact, corpus, served_path=served)

    raw = _prompt(catalog, "c9_raw", tmp_path, static)

    assert "Source: sessions/task-a/p0.jsonl [compiled]" in raw
    assert "Source: sessions/task-a/p1.jsonl\n" in raw


def test_served_evidence_with_too_few_items_is_refused(tmp_path: Path) -> None:
    served = _write(tmp_path / "served.json.gz", _served(items=9))
    with pytest.raises(ValueError, match="fewer than 10"):
        load_served(served, {"task-a"})


def test_served_roster_must_match_the_tasks(tmp_path: Path) -> None:
    served = _write(tmp_path / "served.json.gz", _served(task_ids=("task-a", "task-b")))
    with pytest.raises(ValueError, match="roster mismatch"):
        load_served(served, {"task-a"})


def test_a_served_arm_needs_a_served_artifact(catalog_files, tmp_path: Path) -> None:
    corpus, artifact, static = catalog_files
    catalog = replay.CodeRetrievalReplayCatalog.load(artifact, corpus)
    with pytest.raises(ValueError, match="requires a served evidence artifact"):
        replay.CodeRetrievalReplayAdapter("c9_raw", catalog, tmp_path / "staging", static)


def test_ts1_arms_are_instruction_matched() -> None:
    from scripts.pilot import instruction_arms_are_matched

    assert instruction_arms_are_matched("oneliner", ("code4_replay", "c9_norm", "c9_raw"))
    assert instruction_arms_are_matched("oneliner", ("code3_replay", "code4_replay"))
    assert not instruction_arms_are_matched("oneliner", ("bare", "c9_raw"))
    assert not instruction_arms_are_matched("oneliner", ("c9_raw",))


def test_the_served_digest_is_the_artifacts_bytes(tmp_path: Path) -> None:
    served = _write(tmp_path / "served.json.gz", _served())
    digest, _ = load_served(served, {"task-a"})
    assert digest == hashlib.sha256(served.read_bytes()).hexdigest()
