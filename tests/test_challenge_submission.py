"""Tests for immutable submission descriptors and restricted execution plans."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.challenge_pack import (
    ChallengePackError,
    build_execution_plan,
    load_private_pack,
    load_submission,
)


def _pack(tmp_path: Path):
    root = tmp_path / "pack"
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
    (root / "pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    return load_private_pack(root)


def _submission(tmp_path: Path, **overrides):
    data = {
        "schema": 1,
        "kind": "amb-challenge-submission",
        "submission_id": "entry-a",
        "image": "registry.example/amb/entry@sha256:" + "a" * 64,
        "source_revision": "source-abc123",
        "adapter_api": "amb-challenge-adapter-v1",
        "config_sha256": "b" * 64,
        "network": "model-only",
        "entrypoint": ["/usr/local/bin/amb-entry", "serve"],
    }
    data.update(overrides)
    path = tmp_path / "submission.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_submission_descriptor_loads_and_plan_hides_private_inputs(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = load_submission(_submission(tmp_path))
    plan = build_execution_plan(pack, submission, "task-a").to_dict()
    assert plan["network"] == "model-only"
    assert plan["task_id"] == "task-a"
    assert plan["security"]["cross_task_inputs_mounted"] is False
    assert plan["security"]["private_evaluator_mounted"] is False
    assert plan["security"]["oracle_mounted"] is False
    assert plan["security"]["reference_mounted"] is False
    assert {mount["name"] for mount in plan["mounts"]} == {
        "fixture", "prompt", "corpus", "output"
    }
    mounts = {mount["name"]: mount for mount in plan["mounts"]}
    assert mounts["fixture"]["target"] == "/challenge/task"
    assert mounts["prompt"]["target"] == "/challenge/prompt.txt"
    assert mounts["fixture"]["source"] == "fixtures/task-a"
    assert mounts["prompt"]["source"] == "prompts/task-a.txt"
    assert mounts["corpus"]["source"] == "corpus"


def test_execution_plan_rejects_unknown_task(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = load_submission(_submission(tmp_path))
    with pytest.raises(ChallengePackError, match="unknown challenge task"):
        build_execution_plan(pack, submission, "task-b")


@pytest.mark.parametrize(
    "overrides",
    [
        {"image": "registry.example/amb/entry:latest"},
        {"image": "registry.example/amb/entry@sha256:" + "z" * 64},
        {"network": "host"},
        {"entrypoint": []},
        {"adapter_api": "amb-private-api"},
    ],
)
def test_submission_descriptor_rejects_unsafe_or_mutable_values(
    tmp_path: Path, overrides: dict
):
    with pytest.raises(ChallengePackError):
        load_submission(_submission(tmp_path, **overrides))
