"""CD-1 Stage 1's arms replay a CD-1 Stage 0 collect: cd1_full its 100 served items, cd1_gated the first 10.

Invariants: ``cd1_gated`` shows exactly ``cd1_full``'s first 10 items, rendered identically, and
``cd1_full`` shows all 100 in served order; a task G(0.25) does not gate is refused, since both arms
would show it the same thing; the collect loads only if it is the registered one for its condition
(full digest and arm label), holds exactly 100 items per task, and its recomputed gated set equals
the registered set; a CD-1 arm cannot be built without the collect; its diagnostic names the
collect and the condition.

Red proof, 2026-09-27, each against the named production line with this file unchanged
(``PYTHONDONTWRITEBYTECODE=1``):
- ``build_for_task`` giving ``cd1_gated`` ``full[1:11]``:
  ``test_the_gated_arm_shows_exactly_the_full_arms_first_ten`` fails at the gated ids equality.
- ``build_for_task`` without the gated-task check: ``test_a_task_g_does_not_gate_is_refused`` fails
  at ``DID NOT RAISE``.
- ``load_cd1`` without the gated-set comparison:
  ``test_a_collect_whose_gated_set_differs_from_the_registered_one_is_refused`` fails at ``DID NOT RAISE``.
- ``load_cd1`` without the digest check: ``test_another_file_is_refused_by_its_digest`` fails at
  ``DID NOT RAISE``.
- ``load_cd1`` without the arm-label check:
  ``test_the_other_conditions_collect_is_refused_by_its_arm_label`` fails at ``DID NOT RAISE``.
- ``load_cd1`` requiring at least 10 items instead of exactly 100:
  ``test_a_collect_without_all_100_items_is_refused`` fails at ``DID NOT RAISE``.
- ``CodeRetrievalReplayAdapter`` without the CD-1 collect check: ``test_a_cd1_arm_needs_the_collect``
  fails at ``DID NOT RAISE``.
- ``artifact_digest`` returning ``served_digest`` for the CD-1 arms:
  ``test_the_diagnostic_names_the_collect_and_the_condition`` fails at the digest equality.
Each file was restored byte for byte and all eight passed.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from adapters.code_retrieval_replay import adapter as replay
from adapters.code_retrieval_replay import served
from adapters.code_retrieval_replay.served import Cd1Collect, format_served_evidence
from scripts.retrieval_probe import Window

QUERY = "fix it"


def _artifact(corpus: Path) -> dict:
    """A minimal 091 artifact with two tasks, as the other replay tests build it."""
    hits = [{"rank": rank, "index": 10 - rank, "source_path": f"sessions/task-a/source-{10 - rank}.jsonl",
             "text_sha256": hashlib.sha256(f"window {10 - rank}".encode()).hexdigest()} for rank in range(1, 11)]
    task = {"query_sha256": hashlib.sha256(QUERY.encode()).hexdigest(),
            "code3_replay": {"model": "voyage-code-3", "windows": hits},
            "code4_replay": {"model": "voyage-code-4", "windows": hits}}
    return {
        "schema_version": 1,
        "experiment": "091-voyage-code4-task-solve-evidence",
        "provenance": {"manifest_sha256": hashlib.sha256((corpus / "manifest.json").read_bytes()).hexdigest(),
                       "raw_windows": 10},
        "configuration": {"control_model": "voyage-code-3", "treatment_model": "voyage-code-4",
                          "candidate_k_per_leg": 100, "result_k": 100, "evidence_k": 10, "rrf_k": 60,
                          "window_words": 160, "window_stride": 120},
        "evidence_gate": {"passed": True},
        "tasks": [{"task_id": "task-a", **task}, {"task_id": "task-b", **task}],
    }


def _collect(items: int = 100, arm: str = "CD1P") -> dict:
    def row(task: str, top1: float) -> dict:
        return {"task_id": task, "status": 200, "dense_top1": top1, "top_items": [
            {"id": f"{task}-{rank}", "kind": "raw" if rank % 7 else "compiled",
             "session_id": f"sessions/{task}/s{rank}.jsonl", "created_at": "2026-09-27T10:00:00Z",
             "content": f"[2026-09-27 10:00 UTC] {task} served item {rank}"} for rank in range(items)]}
    return {"arm": arm, "rows": [row("task-a", 0.20), row("task-b", 0.31)]}


@pytest.fixture
def files(tmp_path: Path, monkeypatch):
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


def _register(monkeypatch, path: Path, *, gated=frozenset({"task-a"}), arm: str = "CD1P", digest: str = "") -> None:
    digest = digest or hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(served, "CD1_REGISTERED", {"present": Cd1Collect(sha256=digest, arm=arm, gated=gated)})


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "cd1.json.gz"
    path.write_bytes(gzip.compress(json.dumps(payload).encode()))
    return path


def _catalog(files, collect: Path):
    corpus, artifact, _ = files
    return replay.CodeRetrievalReplayCatalog.load(artifact, corpus, cd1_path=collect, cd1_condition="present")


def _payload(catalog, arm: str, tmp_path: Path, static: Path, task: str = "task-a") -> dict:
    adapter = replay.CodeRetrievalReplayAdapter(arm, catalog, tmp_path / "staging", static)
    spec = adapter.build_for_task(tmp_path / "unused", "ns", task, QUERY)
    return json.loads(spec.append_system_prompt_file.with_name(f"{arm}.payload.json").read_text(encoding="utf-8")) | {
        "_diagnostic": spec.metadata["memory_diagnostic"]}


def test_the_gated_arm_shows_exactly_the_full_arms_first_ten(files, tmp_path, monkeypatch) -> None:
    collect = _write(tmp_path, _collect())
    _register(monkeypatch, collect)
    catalog = _catalog(files, collect)
    full = _payload(catalog, "cd1_full", tmp_path, files[2])
    gated = _payload(catalog, "cd1_gated", tmp_path, files[2])

    assert [i["id"] for i in full["items"]] == [f"task-a-{rank}" for rank in range(100)]
    assert [i["id"] for i in gated["items"]] == [i["id"] for i in full["items"][:10]]
    shown = format_served_evidence(catalog.cd1["task-a"][:10], normalised=False)
    assert gated["injected_text_sha256"] == hashlib.sha256(shown.encode("utf-8")).hexdigest()


def test_a_task_g_does_not_gate_is_refused(files, tmp_path, monkeypatch) -> None:
    collect = _write(tmp_path, _collect())
    _register(monkeypatch, collect)

    with pytest.raises(ValueError, match="does not gate"):
        _payload(_catalog(files, collect), "cd1_gated", tmp_path, files[2], task="task-b")


def test_a_collect_whose_gated_set_differs_from_the_registered_one_is_refused(files, tmp_path, monkeypatch) -> None:
    collect = _write(tmp_path, _collect())
    _register(monkeypatch, collect, gated=frozenset({"task-a", "task-b"}))

    with pytest.raises(ValueError, match="gated set differs"):
        _catalog(files, collect)


def test_another_file_is_refused_by_its_digest(files, tmp_path, monkeypatch) -> None:
    collect = _write(tmp_path, _collect())
    _register(monkeypatch, collect, digest="0" * 64)

    with pytest.raises(ValueError, match="is not the registered one"):
        _catalog(files, collect)


def test_the_other_conditions_collect_is_refused_by_its_arm_label(files, tmp_path, monkeypatch) -> None:
    collect = _write(tmp_path, _collect(arm="CD1A"))
    _register(monkeypatch, collect)

    with pytest.raises(ValueError, match="is arm 'CD1A'"):
        _catalog(files, collect)


def test_a_collect_without_all_100_items_is_refused(files, tmp_path, monkeypatch) -> None:
    collect = _write(tmp_path, _collect(items=99))
    _register(monkeypatch, collect)

    with pytest.raises(ValueError, match="not 100"):
        _catalog(files, collect)


def test_a_cd1_arm_needs_the_collect(files, tmp_path) -> None:
    corpus, artifact, static = files
    catalog = replay.CodeRetrievalReplayCatalog.load(artifact, corpus)

    with pytest.raises(ValueError, match="requires a CD-1 collect"):
        replay.CodeRetrievalReplayAdapter("cd1_full", catalog, tmp_path / "staging", static)


def test_the_diagnostic_names_the_collect_and_the_condition(files, tmp_path, monkeypatch) -> None:
    collect = _write(tmp_path, _collect())
    _register(monkeypatch, collect)
    payload = _payload(_catalog(files, collect), "cd1_gated", tmp_path, files[2])

    assert payload["_diagnostic"]["artifact_sha256"] == hashlib.sha256(collect.read_bytes()).hexdigest()
    assert payload["_diagnostic"]["cd1_condition"] == "present"
    assert payload["_diagnostic"]["cd1_items_shown"] == 10
