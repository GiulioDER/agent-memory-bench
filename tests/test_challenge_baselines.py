"""Tests for the baseline calibration gate."""

from __future__ import annotations

import pytest

from harness.challenge_baselines import ChallengeBaselineError, verify_baseline_ordering


def _manifest(score: float, passed_count: int, submission_id: str | None = None) -> dict:
    return {
        "schema": 1,
        "kind": "amb-challenge-score-manifest",
        "pack_id": "pack-a",
        "scoring_version": "score-a",
        "pack_digest": "b" * 64,
        "rules_digest": "c" * 64,
        "config_sha256": "d" * 64,
        "evaluator_revision": "a" * 40,
        "policy_digest": "e" * 64,
        "submission_id": submission_id or ("entry-a" if score > 0.5 else "entry-b"),
        "image": "registry.example/entry@sha256:" + "a" * 64,
        "task_count": 5,
        "passed_count": passed_count,
        "score": score,
        "tasks": [
            {
                "task_id": f"task-{index}",
                "passed": index < passed_count,
                "checker_returncode": 0,
                "checker_timed_out": False,
            }
            for index in range(5)
        ],
        "private_details_included": False,
    }


def test_baseline_must_beat_deliberately_bad_adapter():
    result = verify_baseline_ordering(_manifest(0.8, 4), _manifest(0.2, 1), minimum_margin=0.5)
    assert result["status"] == "pass"
    assert result["margin"] == 0.6000000000000001


def test_baseline_gate_rejects_missing_ordering():
    with pytest.raises(ChallengeBaselineError, match="ordering failed"):
        verify_baseline_ordering(_manifest(0.4, 2), _manifest(0.4, 2), minimum_margin=0.1)


@pytest.mark.parametrize(
    ("baseline", "bad"),
    [(_manifest(float("nan"), 4), _manifest(0.2, 1)), (_manifest(0.8, 4), _manifest(float("inf"), 1))],
)
def test_baseline_gate_rejects_non_finite_scores(baseline, bad):
    with pytest.raises(ChallengeBaselineError, match="no numeric score"):
        verify_baseline_ordering(baseline, bad)


def test_baseline_gate_rejects_non_finite_margin():
    with pytest.raises(ChallengeBaselineError, match="finite"):
        verify_baseline_ordering(_manifest(0.8, 4), _manifest(0.2, 1), minimum_margin=float("nan"))


def test_baseline_gate_rejects_mismatched_provenance():
    bad = _manifest(0.2, 1)
    bad["policy_digest"] = "f" * 64
    with pytest.raises(ChallengeBaselineError, match="disagree"):
        verify_baseline_ordering(_manifest(0.8, 4), bad)


def test_baseline_gate_rejects_mismatched_evaluator_revision():
    bad = _manifest(0.2, 1)
    bad["evaluator_revision"] = "b" * 40
    with pytest.raises(ChallengeBaselineError, match="disagree"):
        verify_baseline_ordering(_manifest(0.8, 4), bad)


def test_baseline_gate_rejects_manifest_not_bound_to_expected_pack():
    with pytest.raises(ChallengeBaselineError, match="expected pack_id"):
        verify_baseline_ordering(
            _manifest(0.8, 4),
            _manifest(0.2, 1),
            expected_pack_id="different-pack",
        )


def test_baseline_gate_accepts_margin_equal_to_minimum():
    result = verify_baseline_ordering(
        _manifest(0.8, 4), _manifest(0.4, 2), minimum_margin=0.4
    )
    assert result["margin"] == 0.4


def test_baseline_gate_rejects_mutable_image():
    baseline = _manifest(0.8, 4)
    baseline["image"] = "registry.example/entry:latest"
    with pytest.raises(ChallengeBaselineError, match="immutable digest"):
        verify_baseline_ordering(baseline, _manifest(0.2, 1))
