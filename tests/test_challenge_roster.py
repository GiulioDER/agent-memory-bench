from __future__ import annotations

import pytest

from harness.challenge_roster import ChallengeRosterReviewError, validate_roster_review


def _review(pack_digest: str = "a" * 64) -> dict:
    return {
        "schema": 1,
        "kind": "amb-challenge-roster-review",
        "status": "pass",
        "pack_digest": pack_digest,
        "task_count": 1,
        "task_ids": ["task-a"],
        "reviewer_id": "independent-reviewer",
        "independent_review": True,
        "reviewed_at_utc": "2026-09-06T12:00:00Z",
        "checks": {
            name: {"status": "pass", "evidence": f"{name} reviewed"}
            for name in ("capacity", "leakage", "overlap", "findability")
        },
    }


def test_roster_review_accepts_exact_pack_and_task_roster():
    result = validate_roster_review(
        _review(),
        expected_pack_digest="a" * 64,
        expected_task_ids=("task-a",),
    )
    assert result["reviewer_id"] == "independent-reviewer"


def test_roster_review_rejects_different_pack():
    with pytest.raises(ChallengeRosterReviewError, match="does not match the private pack"):
        validate_roster_review(
            _review("b" * 64),
            expected_pack_digest="a" * 64,
            expected_task_ids=("task-a",),
        )


def test_roster_review_rejects_incomplete_findability_check():
    report = _review()
    report["checks"]["findability"] = {"status": "pass", "evidence": ""}
    with pytest.raises(ChallengeRosterReviewError, match="findability.*needs evidence"):
        validate_roster_review(
            report,
            expected_pack_digest="a" * 64,
            expected_task_ids=("task-a",),
        )
