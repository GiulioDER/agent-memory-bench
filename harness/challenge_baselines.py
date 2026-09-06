"""Validate the baseline and deliberately bad adapter score ordering gate."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from .challenge_release import validate_evaluator_revision


class ChallengeBaselineError(ValueError):
    """Baseline calibration inputs do not prove the required ordering."""


def _score(manifest: dict[str, Any], label: str) -> float:
    value = manifest.get("score")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ChallengeBaselineError(f"{label} manifest has no numeric score")
    return float(value)


def validate_public_score_manifest(manifest: dict[str, Any], label: str = "score") -> tuple[str, ...]:
    """Validate the deterministic public manifest fields used for calibration."""

    if not isinstance(manifest, dict):
        raise ChallengeBaselineError(f"{label} manifest must be an object")
    if manifest.get("schema") != 1 or manifest.get("kind") != "amb-challenge-score-manifest":
        raise ChallengeBaselineError(f"{label} manifest has an unsupported schema")
    for field in (
        "pack_id",
        "scoring_version",
        "evaluator_revision",
        "policy_digest",
        "submission_id",
        "image",
    ):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise ChallengeBaselineError(f"{label} manifest is missing {field}")
    try:
        validate_evaluator_revision(manifest["evaluator_revision"])
    except ValueError as error:
        raise ChallengeBaselineError(f"{label} manifest has an invalid evaluator_revision") from error
    if not isinstance(manifest.get("private_details_included"), bool) or manifest["private_details_included"]:
        raise ChallengeBaselineError(f"{label} manifest must be public")
    task_count = manifest.get("task_count")
    passed_count = manifest.get("passed_count")
    if (
        isinstance(task_count, bool)
        or not isinstance(task_count, int)
        or task_count <= 0
        or isinstance(passed_count, bool)
        or not isinstance(passed_count, int)
        or not 0 <= passed_count <= task_count
    ):
        raise ChallengeBaselineError(f"{label} manifest has invalid task counts")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != task_count:
        raise ChallengeBaselineError(f"{label} manifest has invalid task rows")
    task_ids: list[str] = []
    passed_rows = 0
    for row in tasks:
        if not isinstance(row, dict) or set(row) != {
            "task_id",
            "passed",
            "checker_returncode",
            "checker_timed_out",
        }:
            raise ChallengeBaselineError(f"{label} manifest has invalid task rows")
        task_id = row["task_id"]
        if not isinstance(task_id, str) or not task_id.strip() or task_id in task_ids:
            raise ChallengeBaselineError(f"{label} manifest has duplicate or invalid task ids")
        if not isinstance(row["passed"], bool) or not isinstance(row["checker_timed_out"], bool):
            raise ChallengeBaselineError(f"{label} manifest has invalid task outcomes")
        if row["checker_returncode"] is not None and (
            isinstance(row["checker_returncode"], bool)
            or not isinstance(row["checker_returncode"], int)
        ):
            raise ChallengeBaselineError(f"{label} manifest has invalid checker return codes")
        task_ids.append(task_id)
        passed_rows += row["passed"]
    if passed_rows != passed_count:
        raise ChallengeBaselineError(f"{label} manifest passed_count does not match task rows")
    score = _score(manifest, label)
    if not 0 <= score <= 1 or score != passed_count / task_count:
        raise ChallengeBaselineError(f"{label} manifest score does not match task rows")
    return tuple(task_ids)


def verify_baseline_ordering(
    baseline: dict[str, Any],
    deliberately_bad: dict[str, Any],
    *,
    minimum_margin: float = 0.0,
    expected_pack_id: str | None = None,
    expected_policy_digest: str | None = None,
    expected_scoring_version: str | None = None,
    expected_evaluator_revision: str | None = None,
    expected_task_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Require the fixed baseline to beat the deliberately bad adapter."""

    if not math.isfinite(minimum_margin) or minimum_margin < 0:
        raise ChallengeBaselineError("minimum margin must be finite and non negative")
    baseline_task_ids = validate_public_score_manifest(baseline, "baseline")
    bad_task_ids = validate_public_score_manifest(deliberately_bad, "deliberately bad")
    comparable_fields = (
        "pack_id",
        "scoring_version",
        "evaluator_revision",
        "policy_digest",
        "task_count",
    )
    mismatches = [field for field in comparable_fields if baseline.get(field) != deliberately_bad.get(field)]
    if mismatches:
        raise ChallengeBaselineError(f"baseline manifests disagree on: {mismatches}")
    if baseline_task_ids != bad_task_ids:
        raise ChallengeBaselineError("baseline manifests have different task rosters")
    expected = {
        "pack_id": expected_pack_id,
        "policy_digest": expected_policy_digest,
        "scoring_version": expected_scoring_version,
        "evaluator_revision": expected_evaluator_revision,
    }
    for field, value in expected.items():
        if value is not None and baseline.get(field) != value:
            raise ChallengeBaselineError(f"baseline manifest does not match expected {field}")
    if expected_task_ids is not None and baseline_task_ids != tuple(expected_task_ids):
        raise ChallengeBaselineError("baseline manifest does not match the private task roster")
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
