"""Tests for private checker execution and public score manifest redaction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.challenge_pack import load_private_pack, load_submission
from harness.challenge_scoring import (
    ChallengeScoringError,
    ChallengeTaskScore,
    build_score_manifest,
    run_private_checker,
    write_score_manifest,
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
    (root / "checkers/task-a/checker.py").write_text(
        "def check(workdir, oracle_dir):\n"
        "    ok = (workdir / 'answer.txt').read_text() == (oracle_dir / 'input.txt').read_text()\n"
        "    return ok, 'private oracle detail'\n",
        encoding="utf-8",
    )
    (root / "pack.json").write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )
    return load_private_pack(root)


def _submission(tmp_path: Path):
    path = tmp_path / "submission.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "amb-challenge-submission",
                "submission_id": "entry-a",
                "image": "registry.example/amb/entry@sha256:" + "a" * 64,
                "source_revision": "source-abc123",
                "adapter_api": "amb-challenge-adapter-v1",
                "config_sha256": "b" * 64,
                "network": "none",
                "entrypoint": ["/usr/local/bin/amb-entry", "serve"],
            }
        ),
        encoding="utf-8",
    )
    return load_submission(path)


def test_private_checker_runs_after_task_and_public_manifest_redacts_verdict(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = _submission(tmp_path)
    workdir = tmp_path / "output"
    workdir.mkdir()
    (workdir / "answer.txt").write_text("placeholder", encoding="utf-8")
    score = run_private_checker(pack.tasks[0], workdir)
    assert score.passed is True
    assert score.verdict == "private oracle detail"
    public = build_score_manifest(
        pack, submission, [score], evaluator_revision="a" * 40, public=True
    )
    assert public["score"] == 1.0
    assert "verdict" not in public["tasks"][0]
    assert str(pack.root) not in json.dumps(public)


def test_score_manifest_requires_exact_task_coverage(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = _submission(tmp_path)
    with pytest.raises(ChallengeScoringError, match="exactly one result"):
        build_score_manifest(pack, submission, [], evaluator_revision="a" * 40)


def test_score_manifest_write_is_stable(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = _submission(tmp_path)
    workdir = tmp_path / "output"
    workdir.mkdir()
    (workdir / "answer.txt").write_text("wrong", encoding="utf-8")
    score = run_private_checker(pack.tasks[0], workdir)
    manifest = build_score_manifest(
        pack, submission, [score], evaluator_revision="a" * 40, public=True
    )
    target = tmp_path / "manifest.json"
    write_score_manifest(target, manifest)
    first = target.read_bytes()
    write_score_manifest(target, manifest)
    assert target.read_bytes() == first


def test_score_manifest_write_rejects_replacement_data(tmp_path: Path):
    target = tmp_path / "manifest.json"
    write_score_manifest(target, {"score": 1.0})
    with pytest.raises(ChallengeScoringError, match="different data"):
        write_score_manifest(target, {"score": 0.0})


def test_score_manifest_omits_run_specific_checker_timing(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = _submission(tmp_path)
    first = ChallengeTaskScore(
        task_id="task-a",
        passed=True,
        verdict="private",
        checker_returncode=0,
        checker_timed_out=False,
        checker_wall_s=0.1,
    )
    second = ChallengeTaskScore(
        task_id="task-a",
        passed=True,
        verdict="private",
        checker_returncode=0,
        checker_timed_out=False,
        checker_wall_s=9.9,
    )
    assert build_score_manifest(
        pack, submission, [first], evaluator_revision="a" * 40, public=True
    ) == build_score_manifest(
        pack, submission, [second], evaluator_revision="a" * 40, public=True
    )
