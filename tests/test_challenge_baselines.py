"""Tests for the baseline calibration gate."""

from __future__ import annotations

import pytest

from harness.challenge_baselines import ChallengeBaselineError, verify_baseline_ordering


def test_baseline_must_beat_deliberately_bad_adapter():
    result = verify_baseline_ordering({"score": 0.8}, {"score": 0.2}, minimum_margin=0.5)
    assert result["status"] == "pass"
    assert result["margin"] == 0.6000000000000001


def test_baseline_gate_rejects_missing_ordering():
    with pytest.raises(ChallengeBaselineError, match="ordering failed"):
        verify_baseline_ordering({"score": 0.5}, {"score": 0.5})
