"""Tests for deterministic private release hashing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.challenge_pack import load_private_pack
from harness.challenge_policy import load_policy
from harness.challenge_release import (
    build_release_manifest,
    hash_private_pack,
    write_release_manifest,
)


def _pack(root: Path):
    for relative in (
        "corpus/session.jsonl",
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
    return load_private_pack(root)


def test_release_manifest_changes_when_private_bytes_change(tmp_path: Path):
    pack = _pack(tmp_path / "pack")
    policy = load_policy(Path(__file__).parents[1] / "preregistration" / "challenge_policy.json")
    first = build_release_manifest(pack, policy)
    (pack.root / "oracles/task-a/value.txt").write_text("changed", encoding="utf-8")
    changed_pack = load_private_pack(pack.root)
    second = build_release_manifest(changed_pack, policy)
    assert first["pack_digest"] != second["pack_digest"]
    assert first["policy_digest"] == second["policy_digest"]


def test_pack_hash_is_stable_for_same_bytes(tmp_path: Path):
    pack = _pack(tmp_path / "pack")
    assert hash_private_pack(pack) == hash_private_pack(load_private_pack(pack.root))


def test_release_manifest_binds_evaluator_revision(tmp_path: Path):
    pack = _pack(tmp_path / "pack")
    policy = load_policy(Path(__file__).parents[1] / "preregistration" / "challenge_policy.json")
    manifest = build_release_manifest(pack, policy, evaluator_revision="a" * 40)
    assert manifest["evaluator_revision"] == "a" * 40
    with pytest.raises(ValueError, match="commit hash"):
        build_release_manifest(pack, policy, evaluator_revision="dirty")


def test_final_release_requires_pack_preparer_identity(tmp_path: Path):
    pack = _pack(tmp_path / "pack")
    policy = load_policy(Path(__file__).parents[1] / "preregistration" / "challenge_policy.json")
    with pytest.raises(ValueError, match="prepared_by"):
        build_release_manifest(pack, policy, require_pack_preparer_id=True)

    pack.manifest["prepared_by"] = "pack-author"
    release = build_release_manifest(pack, policy, require_pack_preparer_id=True)
    assert release["prepared_by"] == "pack-author"


def test_release_manifest_cannot_be_overwritten(tmp_path: Path):
    target = tmp_path / "release.json"
    write_release_manifest(target, {"version": 1})
    with pytest.raises(ValueError, match="already exists"):
        write_release_manifest(target, {"version": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"version": 1}
