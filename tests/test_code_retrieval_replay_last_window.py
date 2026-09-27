"""TS-1 amendment A1's arms replay RE-call's LW-1 collect: c9_raw2 its top 10, c9_lw that plus LW-1's windows.

Invariants: ``c9_raw2`` shows exactly the LW-1 collect's top 10 as served; ``c9_lw`` shows the same
10 and then the manifest's appended windows at ranks 11 onward, in manifest order, so the two differ
only in those; the manifest must name the collect by digest and list the served items at ranks 11
onward, or nothing loads; an A1 arm cannot be built without both files; its diagnostic carries the
LW-1 collect's digest and the manifest's, never TS-1's served artifact.

Red proof, 2026-09-27, each against the named production line with this file unchanged
(``PYTHONDONTWRITEBYTECODE=1``):
- ``build_for_task`` giving ``c9_lw`` only ``evidence.top``:
  ``test_lw_arm_shows_the_top_ten_then_the_appended_windows`` fails at the rank 11 ``in``.
- ``build_for_task`` giving ``c9_raw2`` the appended windows too:
  ``test_raw2_arm_shows_only_the_same_top_ten`` fails at ``not in``.
- ``load_last_window_served`` without the ``served_sha256`` check:
  ``test_a_manifest_for_another_collect_is_refused`` fails at ``DID NOT RAISE``.
- ``load_last_window_served`` without the id comparison after rank 10:
  ``test_manifest_ids_must_be_the_served_items_after_rank_ten`` fails at ``DID NOT RAISE``.
- ``CodeRetrievalReplayAdapter`` without the last-window check:
  ``test_an_a1_arm_needs_the_last_window_files`` fails at ``DID NOT RAISE``.
- ``artifact_digest`` returning ``served_digest`` for the A1 arms:
  ``test_a1_diagnostic_names_the_lw_collect_and_its_manifest`` fails at the digest assertion.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from adapters.code_retrieval_replay import adapter as replay
from adapters.code_retrieval_replay.served import LW_MANIFEST_SCHEMA, load_last_window_served
from scripts.retrieval_probe import Window

HEADER = "[2026-09-26 10:00 UTC] "
APPENDED = ["last-B", "last-A"]


def _artifact(corpus: Path) -> dict:
    """A minimal 091 artifact, as ``tests/test_code_retrieval_replay_served.py`` builds it."""
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


def _served(items: int = 10) -> dict:
    return {"rows": [{"task_id": "task-a", "status": 200, "top_items": [
        {"id": f"i{rank}", "kind": "raw", "session_id": f"sessions/task-a/p{rank}.jsonl",
         "created_at": "2026-09-26T10:00:00Z", "content": f"{HEADER}Keep APP_MAX_RETRIES at {rank}"}
        for rank in range(items)]}]}


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


def _lw_collect(items_after: int = 4) -> dict:
    """Ten top items, then LW-1's two appended windows, then the next-ranked ones."""
    payload = _served(items=10)
    row = payload["rows"][0]
    for n, item_id in enumerate(APPENDED):
        row["top_items"].append({"id": item_id, "kind": "raw", "session_id": f"sessions/task-a/{item_id}.jsonl",
                                 "created_at": "2026-09-26T10:00:00Z",
                                 "content": f"{HEADER}decision: final {item_id} {n}"})
    for n in range(items_after - len(APPENDED)):
        row["top_items"].append({"id": f"next-{n}", "kind": "raw", "session_id": "sessions/task-a/next.jsonl",
                                 "created_at": "2026-09-26T10:00:00Z", "content": f"{HEADER}next ranked {n}"})
    return payload


def _manifest(path: Path, served: Path, ids=None, *, digest: str | None = None) -> Path:
    path.write_text(json.dumps({
        "schema": LW_MANIFEST_SCHEMA,
        "served_sha256": digest or hashlib.sha256(served.read_bytes()).hexdigest(),
        "tasks": {"task-a": APPENDED if ids is None else ids},
    }), encoding="utf-8")
    return path


def _files(tmp_path: Path, ids=None, *, digest: str | None = None) -> tuple[Path, Path]:
    served = _write(tmp_path / "lw.json.gz", _lw_collect())
    return served, _manifest(tmp_path / "lw-manifest.json", served, ids, digest=digest)


def _spec(catalog, arm: str, tmp_path: Path, static: Path):
    adapter = replay.CodeRetrievalReplayAdapter(arm, catalog, tmp_path / "staging", static)
    return adapter.build_for_task(tmp_path / "unused", "ns", "task-a", "fix it")


def _prompt(catalog, arm: str, tmp_path: Path, static: Path) -> str:
    return Path(_spec(catalog, arm, tmp_path, static).append_system_prompt_file).read_text(encoding="utf-8")


def _catalog(corpus: Path, artifact: Path, tmp_path: Path, **served):
    lw, manifest = _files(tmp_path)
    return replay.CodeRetrievalReplayCatalog.load(artifact, corpus, last_window_path=lw,
                                                  last_window_manifest_path=manifest, **served)


def test_lw_arm_shows_the_top_ten_then_the_appended_windows(catalog_files, tmp_path: Path) -> None:
    corpus, artifact, static = catalog_files
    catalog = _catalog(corpus, artifact, tmp_path)

    text = _prompt(catalog, "c9_lw", tmp_path, static)

    assert "Keep APP_MAX_RETRIES at 9" in text
    assert "[Retrieved memory rank 11]\nSource: sessions/task-a/last-B.jsonl\n" in text
    assert text.index("decision: final last-B") < text.index("decision: final last-A")
    assert "[Retrieved memory rank 12]" in text and "[Retrieved memory rank 13]" not in text
    assert "next ranked" not in text


def test_raw2_arm_shows_only_the_same_top_ten(catalog_files, tmp_path: Path) -> None:
    corpus, artifact, static = catalog_files
    catalog = _catalog(corpus, artifact, tmp_path)

    raw2 = _prompt(catalog, "c9_raw2", tmp_path, static)
    lw = _prompt(catalog, "c9_lw", tmp_path, static)

    assert "Keep APP_MAX_RETRIES at 9" in raw2
    assert "[Retrieved memory rank 11]" not in raw2
    assert lw.startswith(raw2.split("[Retrieved memory rank 10]")[0])


def test_a_manifest_for_another_collect_is_refused(tmp_path: Path) -> None:
    served, manifest = _files(tmp_path, digest="0" * 64)
    with pytest.raises(ValueError, match="does not describe this served artifact"):
        load_last_window_served(served, manifest, {"task-a"})


def test_manifest_ids_must_be_the_served_items_after_rank_ten(tmp_path: Path) -> None:
    served, manifest = _files(tmp_path, ids=["last-A", "last-B"])
    with pytest.raises(ValueError, match="not the manifest's last windows"):
        load_last_window_served(served, manifest, {"task-a"})


def test_a_manifest_roster_must_match_the_tasks(tmp_path: Path) -> None:
    served = _write(tmp_path / "lw.json.gz", _lw_collect())
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"schema": LW_MANIFEST_SCHEMA,
                                    "served_sha256": hashlib.sha256(served.read_bytes()).hexdigest(),
                                    "tasks": {"task-a": APPENDED, "task-b": []}}), encoding="utf-8")
    with pytest.raises(ValueError, match="roster"):
        load_last_window_served(served, manifest, {"task-a"})


def test_an_a1_arm_needs_the_last_window_files(catalog_files, tmp_path: Path) -> None:
    corpus, artifact, static = catalog_files
    served = _write(tmp_path / "served.json.gz", _served())
    catalog = replay.CodeRetrievalReplayCatalog.load(artifact, corpus, served_path=served)
    for arm in ("c9_raw2", "c9_lw"):
        with pytest.raises(ValueError, match="requires the last-window artifact"):
            replay.CodeRetrievalReplayAdapter(arm, catalog, tmp_path / "staging", static)


def test_the_artifact_and_manifest_load_together_or_not_at_all(catalog_files, tmp_path: Path) -> None:
    corpus, artifact, _ = catalog_files
    lw, _manifest_path = _files(tmp_path)
    with pytest.raises(ValueError, match="together or not at all"):
        replay.CodeRetrievalReplayCatalog.load(artifact, corpus, last_window_path=lw)


def test_a1_diagnostic_names_the_lw_collect_and_its_manifest(catalog_files, tmp_path: Path) -> None:
    corpus, artifact, static = catalog_files
    served = _write(tmp_path / "served.json.gz", _served())
    catalog = _catalog(corpus, artifact, tmp_path, served_path=served)
    lw_digest = hashlib.sha256((tmp_path / "lw.json.gz").read_bytes()).hexdigest()
    manifest_digest = hashlib.sha256((tmp_path / "lw-manifest.json").read_bytes()).hexdigest()

    for arm in ("c9_raw2", "c9_lw"):
        diagnostic = _spec(catalog, arm, tmp_path, static).metadata["memory_diagnostic"]
        assert diagnostic["artifact_sha256"] == lw_digest
        assert diagnostic["last_window_manifest_sha256"] == manifest_digest
        assert diagnostic["model"] == "re-call-c9-last-window"
    served_diagnostic = _spec(catalog, "c9_raw", tmp_path, static).metadata["memory_diagnostic"]
    assert served_diagnostic["artifact_sha256"] == hashlib.sha256(served.read_bytes()).hexdigest()
    assert "last_window_manifest_sha256" not in served_diagnostic


def test_a1_arms_are_instruction_matched_with_ts1s() -> None:
    from scripts.pilot import instruction_arms_are_matched

    assert instruction_arms_are_matched("oneliner", ("code4_replay", "c9_norm", "c9_raw", "c9_raw2", "c9_lw"))
    assert not instruction_arms_are_matched("oneliner", ("bare", "c9_lw"))
