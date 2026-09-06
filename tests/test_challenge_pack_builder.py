"""Tests for private pack materialization boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.challenge_pack_builder import ChallengePackBuildError, materialize_private_pack


def _source(root: Path) -> Path:
    for relative in (
        "corpus/session.txt",
        "fixtures/task-a/input.txt",
        "prompts/task-a.txt",
        "checkers/task-a/checker.py",
        "oracles/task-a/value.txt",
        "references/task-a/answer.txt",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")
    (root / "pack.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "amb-private-evaluation-pack",
                "visibility": "private",
                "pack_id": "pack-a",
                "source_public_commit": "commit-a",
                "scoring_version": "score-a",
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
        ),
        encoding="utf-8",
    )
    return root


def test_materialize_private_pack_copies_and_validates(tmp_path: Path):
    pack = materialize_private_pack(_source(tmp_path / "source"), tmp_path / "destination")
    assert pack.manifest["pack_id"] == "pack-a"
    assert (pack.root / "oracles/task-a/value.txt").is_file()


def test_materialize_private_pack_rejects_nonempty_destination(tmp_path: Path):
    source = _source(tmp_path / "source")
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "existing").write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(ChallengePackBuildError, match="start empty"):
        materialize_private_pack(source, destination)


def test_materialize_private_pack_rejects_public_source():
    from harness.challenge_pack import PUBLIC_REPO_ROOT

    with pytest.raises(ChallengePackBuildError, match="outside the public repository"):
        materialize_private_pack(PUBLIC_REPO_ROOT, Path("/tmp/unused-private-pack"))


def test_materialize_private_pack_rejects_source_containing_public_repository(tmp_path: Path):
    from harness.challenge_pack import PUBLIC_REPO_ROOT

    source_parent = PUBLIC_REPO_ROOT.parent
    with pytest.raises(ChallengePackBuildError, match="outside the public repository"):
        materialize_private_pack(source_parent, tmp_path / "destination")


def test_materialize_private_pack_rejects_corpus_leakage(tmp_path: Path):
    source = _source(tmp_path / "source")
    (source / "corpus/session.txt").write_text("prompts/task-a.txt", encoding="utf-8")

    with pytest.raises(ChallengePackBuildError, match="corpus audit failed"):
        materialize_private_pack(source, tmp_path / "destination")
