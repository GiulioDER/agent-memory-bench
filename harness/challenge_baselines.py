"""Validate the baseline and deliberately bad adapter score ordering gate."""

from __future__ import annotations

import math
from typing import Any


class ChallengeBaselineError(ValueError):
    """Baseline calibration inputs do not prove the required ordering."""


def _score(manifest: dict[str, Any], label: str) -> float:
    value = manifest.get("score")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ChallengeBaselineError(f"{label} manifest has no numeric score")
    return float(value)


def verify_baseline_ordering(
    baseline: dict[str, Any],
    deliberately_bad: dict[str, Any],
    *,
    minimum_margin: float = 0.0,
) -> dict[str, Any]:
    """Require the fixed baseline to beat the deliberately bad adapter."""

    if not math.isfinite(minimum_margin) or minimum_margin < 0:
        raise ChallengeBaselineError("minimum margin must be finite and non negative")
    baseline_score = _score(baseline, "baseline")
    bad_score = _score(deliberately_bad, "deliberately bad")
    margin = baseline_score - bad_score
    if margin <= minimum_margin:
        raise ChallengeBaselineError(
            f"baseline ordering failed: baseline={baseline_score}, bad={bad_score}, "
            f"margin={margin}, required={minimum_margin}"
        )
    return {
        "status": "pass",
        "baseline_score": baseline_score,
        "deliberately_bad_score": bad_score,
        "margin": margin,
        "minimum_margin": minimum_margin,
    }
