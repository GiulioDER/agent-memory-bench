"""Tests for deterministic challenge ranking and tie handling."""

from __future__ import annotations

import pytest

from harness.challenge_ranking import ChallengeRankingError, rank_challenge_entries


def _manifest(submission_id: str, score: float, passed: tuple[bool, bool]) -> dict:
    return {
        "schema": 1,
        "kind": "amb-challenge-score-manifest",
        "pack_id": "pack-a",
        "scoring_version": "score-a",
        "evaluator_revision": "a" * 40,
        "policy_digest": "policy-a",
        "submission_id": submission_id,
        "image": "registry.example/entry@sha256:" + "a" * 64,
        "task_count": 2,
        "passed_count": sum(passed),
        "score": score,
        "tasks": [
            {
                "task_id": task_id,
                "passed": value,
                "checker_returncode": 0,
                "checker_timed_out": False,
            }
            for task_id, value in zip(("task-a", "task-b"), passed)
        ],
        "private_details_included": False,
    }


def _rules(tie_breaker_task_ids: list[str]) -> dict:
    return {
        "status": "final",
        "winner_count": 1,
        "tie_breaker_task_ids": tie_breaker_task_ids,
        "excluded_submission_ids": ["sponsor-reference"],
    }


def test_ranking_uses_frozen_tie_breaker_order():
    result = rank_challenge_entries(
        [_manifest("entry-a", 0.5, (True, False)), _manifest("entry-b", 0.5, (False, True))],
        _rules(["task-a"]),
    )
    assert result["status"] == "ranked"
    assert result["winner_submission_ids"] == ["entry-a"]
    assert [entry["rank"] for entry in result["entries"]] == [1, 2]


def test_ranking_does_not_silently_break_an_unresolved_tie():
    result = rank_challenge_entries(
        [_manifest("entry-a", 0.5, (True, False)), _manifest("entry-b", 0.5, (True, False))],
        _rules(["task-a"]),
    )
    assert result["status"] == "tie"
    assert result["winner_submission_ids"] == []
    assert result["boundary_tie_submission_ids"] == ["entry-a", "entry-b"]


def test_ranking_rejects_provenance_mismatch():
    bad = _manifest("entry-b", 0.5, (False, True))
    bad["policy_digest"] = "other-policy"
    with pytest.raises(ChallengeRankingError, match="policy_digest"):
        rank_challenge_entries(
            [_manifest("entry-a", 0.5, (True, False)), bad],
            _rules(["task-a"]),
            expected_policy_digest="policy-a",
        )


def test_ranking_rejects_mixed_evaluator_revisions():
    bad = _manifest("entry-b", 0.5, (False, True))
    bad["evaluator_revision"] = "b" * 40
    with pytest.raises(ChallengeRankingError, match="different evaluator revisions"):
        rank_challenge_entries(
            [_manifest("entry-a", 0.5, (True, False)), bad],
            _rules(["task-a"]),
        )


def test_ranking_rejects_excluded_submission():
    with pytest.raises(ChallengeRankingError, match="excluded submission"):
        rank_challenge_entries(
            [_manifest("sponsor-reference", 1.0, (True, True))],
            _rules(["task-a"]),
        )
