"""Structural tests for the private challenge pack boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.challenge_pack import ChallengePackError, load_private_pack


def _write_pack(root: Path, **overrides) -> Path:
    root.mkdir()
    for relative in (
        "corpus/manifest.json",
        "fixtures/task-a/README.md",
        "prompts/task-a.txt",
        "checkers/task-a/checker.py",
        "oracles/task-a/input.txt",
        "references/task-a/informed.py",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder", encoding="utf-8")
    manifest = {
        "schema": 1,
        "kind": "amb-private-evaluation-pack",
        "visibility": "private",
        "pack_id": "challenge-test-001",
        "source_public_commit": "abc123",
        "scoring_version": "score-1",
        "corpus": "corpus",
        "tasks": [
            {
                "task_id": "task-a",
                "fixture": "fixtures/task-a",
                "prompt": "prompts/task-a.txt",
                "checker": "checkers/task-a/checker.py",
                "oracle": "oracles/task-a",
                "reference": "references/task-a",
            }
        ],
    }
    manifest.update(overrides)
    (root / "pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_valid_private_pack_loads(tmp_path: Path):
    pack = load_private_pack(_write_pack(tmp_path / "pack"))
    assert pack.manifest["pack_id"] == "challenge-test-001"
    assert [task.task_id for task in pack.tasks] == ["task-a"]


def test_public_repository_is_never_a_private_pack():
    from harness.challenge_pack import PUBLIC_REPO_ROOT

    with pytest.raises(ChallengePackError, match="public repository"):
        load_private_pack(PUBLIC_REPO_ROOT)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("oracle", "../outside"),
        ("checker", "/tmp/checker.py"),
        ("prompt", "C:/outside.txt"),
        ("reference", "references\\task-a"),
    ],
)
def test_task_paths_must_be_portable_and_contained(tmp_path: Path, field: str, value: str):
    pack = _write_pack(tmp_path / "pack")
    manifest = json.loads((pack / "pack.json").read_text(encoding="utf-8"))
    manifest["tasks"][0][field] = value
    (pack / "pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ChallengePackError):
        load_private_pack(pack)


def test_missing_private_oracle_is_rejected(tmp_path: Path):
    pack = _write_pack(tmp_path / "pack")
    (pack / "oracles/task-a/input.txt").unlink()
    (pack / "oracles/task-a").rmdir()
    with pytest.raises(ChallengePackError, match="does not exist"):
        load_private_pack(pack)


def test_missing_corpus_is_rejected(tmp_path: Path):
    pack = _write_pack(tmp_path / "pack")
    manifest = json.loads((pack / "pack.json").read_text(encoding="utf-8"))
    manifest.pop("corpus")
    (pack / "pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ChallengePackError, match="task 'corpus'"):
        load_private_pack(pack)


def test_task_private_inputs_must_not_be_reused_between_tasks(tmp_path: Path):
    pack = _write_pack(tmp_path / "pack")
    manifest = json.loads((pack / "pack.json").read_text(encoding="utf-8"))
    manifest["tasks"].append(dict(manifest["tasks"][0], task_id="task-b"))
    (pack / "pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ChallengePackError, match="paths overlap"):
        load_private_pack(pack)
