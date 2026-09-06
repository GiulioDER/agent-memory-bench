"""Validate the independent task roster review required before a prize run."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .challenge_release import validate_sha256_digest

REVIEW_KIND = "amb-challenge-roster-review"
REVIEW_SCHEMA = 1
REVIEW_CHECKS = ("capacity", "leakage", "overlap", "findability")


class ChallengeRosterReviewError(ValueError):
    """The roster review is missing, malformed or bound to different private material."""


def validate_roster_review(
    data: Any,
    *,
    expected_pack_digest: str,
    expected_task_ids: Iterable[str],
    expected_pack_preparer_id: str | None = None,
) -> dict[str, Any]:
    """Validate an independent pass report for the frozen private task roster."""

    if not isinstance(data, dict):
        raise ChallengeRosterReviewError("roster review must contain an object")
    if data.get("schema") != REVIEW_SCHEMA or data.get("kind") != REVIEW_KIND:
        raise ChallengeRosterReviewError("unsupported roster review")
    if data.get("status") != "pass":
        raise ChallengeRosterReviewError("roster review does not record a pass")
    try:
        expected_pack_digest = validate_sha256_digest(expected_pack_digest, "expected pack_digest")
        pack_digest = validate_sha256_digest(data.get("pack_digest"), "roster review pack_digest")
    except ValueError as error:
        raise ChallengeRosterReviewError(str(error)) from error
    if pack_digest != expected_pack_digest:
        raise ChallengeRosterReviewError("roster review does not match the private pack")

    task_ids = tuple(expected_task_ids)
    if data.get("task_ids") != list(task_ids):
        raise ChallengeRosterReviewError("roster review task ids do not match the private pack")
    if data.get("task_count") != len(task_ids) or not task_ids:
        raise ChallengeRosterReviewError("roster review has an invalid task count")
    if not isinstance(data.get("reviewer_id"), str) or not data["reviewer_id"].strip():
        raise ChallengeRosterReviewError("roster review needs a reviewer_id")
    if expected_pack_preparer_id is not None:
        if (
            not isinstance(expected_pack_preparer_id, str)
            or not expected_pack_preparer_id.strip()
        ):
            raise ChallengeRosterReviewError(
                "private pack prepared_by must be a non empty string"
            )
        if data.get("pack_preparer_id") != expected_pack_preparer_id:
            raise ChallengeRosterReviewError(
                "roster review does not identify the private pack preparer"
            )
        if data["reviewer_id"] == expected_pack_preparer_id:
            raise ChallengeRosterReviewError(
                "roster reviewer must be different from the private pack preparer"
            )
    if data.get("independent_review") is not True:
        raise ChallengeRosterReviewError("roster review must be independently reviewed")
    if not isinstance(data.get("reviewed_at_utc"), str) or not data["reviewed_at_utc"].strip():
        raise ChallengeRosterReviewError("roster review needs reviewed_at_utc")

    checks = data.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(REVIEW_CHECKS):
        raise ChallengeRosterReviewError(
            "roster review must cover capacity, leakage, overlap and findability"
        )
    for name in REVIEW_CHECKS:
        check = checks[name]
        if not isinstance(check, dict) or check.get("status") != "pass":
            raise ChallengeRosterReviewError(f"roster review check {name!r} did not pass")
        evidence = check.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ChallengeRosterReviewError(f"roster review check {name!r} needs evidence")
    return data
