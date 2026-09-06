"""Rank challenge score manifests with deterministic tie breaker handling."""

from __future__ import annotations

from typing import Any

from .challenge_baselines import ChallengeBaselineError, validate_public_score_manifest
from .challenge_rules import ChallengeRulesError, validate_rules_for_task_ids


class ChallengeRankingError(ValueError):
    """The score manifests cannot be ranked under the final challenge rules."""


def rank_challenge_entries(
    manifests: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    rules: dict[str, Any],
    *,
    expected_pack_id: str | None = None,
    expected_policy_digest: str | None = None,
    expected_scoring_version: str | None = None,
    expected_evaluator_revision: str | None = None,
    expected_task_ids: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Return deterministic ranks without silently selecting an unresolved tie."""

    if rules.get("status") != "final":
        raise ChallengeRulesError("ranking requires final challenge rules")
    tie_breaker_ids = rules.get("tie_breaker_task_ids")
    if not isinstance(tie_breaker_ids, list) or not all(isinstance(value, str) for value in tie_breaker_ids):
        raise ChallengeRulesError("ranking requires a valid tie breaker task list")
    if not tie_breaker_ids or len(set(tie_breaker_ids)) != len(tie_breaker_ids):
        raise ChallengeRulesError("ranking requires unique tie breaker task ids")
    excluded_submission_ids = rules.get("excluded_submission_ids")
    if not isinstance(excluded_submission_ids, list) or not all(
        isinstance(value, str) and value.strip() for value in excluded_submission_ids
    ):
        raise ChallengeRulesError("ranking requires excluded submission ids")
    if len(set(excluded_submission_ids)) != len(excluded_submission_ids):
        raise ChallengeRulesError("ranking requires unique excluded submission ids")
    if not manifests:
        raise ChallengeRankingError("at least one score manifest is required")

    entries: list[dict[str, Any]] = []
    seen_submission_ids: set[str] = set()
    roster: tuple[str, ...] | None = None
    evaluator_revision: str | None = None
    for manifest in manifests:
        try:
            task_ids = validate_public_score_manifest(manifest)
        except ChallengeBaselineError as error:
            raise ChallengeRankingError(str(error)) from error
        if roster is None:
            roster = task_ids
        elif roster != task_ids:
            raise ChallengeRankingError("score manifests have different task rosters")
        if evaluator_revision is None:
            evaluator_revision = manifest["evaluator_revision"]
        elif evaluator_revision != manifest["evaluator_revision"]:
            raise ChallengeRankingError("score manifests use different evaluator revisions")
        submission_id = manifest["submission_id"]
        if submission_id in excluded_submission_ids:
            raise ChallengeRankingError(
                f"excluded submission id cannot be ranked: {submission_id}"
            )
        if submission_id in seen_submission_ids:
            raise ChallengeRankingError(f"duplicate submission id: {submission_id}")
        seen_submission_ids.add(submission_id)
        if expected_pack_id is not None and manifest["pack_id"] != expected_pack_id:
            raise ChallengeRankingError("score manifest does not match expected pack_id")
        if expected_policy_digest is not None and manifest["policy_digest"] != expected_policy_digest:
            raise ChallengeRankingError("score manifest does not match expected policy_digest")
        if expected_scoring_version is not None and manifest["scoring_version"] != expected_scoring_version:
            raise ChallengeRankingError("score manifest does not match expected scoring_version")
        if (
            expected_evaluator_revision is not None
            and manifest["evaluator_revision"] != expected_evaluator_revision
        ):
            raise ChallengeRankingError("score manifest does not match expected evaluator_revision")
        entries.append(manifest)
    assert roster is not None
    if expected_task_ids is not None and roster != expected_task_ids:
        raise ChallengeRankingError("score manifests do not match the private task roster")
    try:
        validate_rules_for_task_ids(rules, roster)
    except ChallengeRulesError as error:
        raise ChallengeRankingError(str(error)) from error

    task_rows = {
        manifest["submission_id"]: {row["task_id"]: row for row in manifest["tasks"]}
        for manifest in entries
    }
    tie_ids = tuple(tie_breaker_ids)
    ordered = sorted(
        entries,
        key=lambda manifest: (
            -manifest["score"],
            tuple(-int(task_rows[manifest["submission_id"]][task_id]["passed"]) for task_id in tie_ids),
        ),
    )
    keys = [
        (
            manifest["score"],
            tuple(task_rows[manifest["submission_id"]][task_id]["passed"] for task_id in tie_ids),
        )
        for manifest in ordered
    ]
    rows: list[dict[str, Any]] = []
    for index, manifest in enumerate(ordered):
        rank = 1 + sum(keys[prior] != keys[index] for prior in range(index))
        rows.append(
            {
                "rank": rank,
                "submission_id": manifest["submission_id"],
                "score": manifest["score"],
                "tie_breaker": [
                    {"task_id": task_id, "passed": task_rows[manifest["submission_id"]][task_id]["passed"]}
                    for task_id in tie_ids
                ],
            }
        )
    winner_count = rules["winner_count"]
    if not isinstance(winner_count, int) or isinstance(winner_count, bool) or not 1 <= winner_count <= len(rows):
        raise ChallengeRankingError("winner_count must fit the supplied entry set")
    boundary_key = keys[winner_count - 1]
    boundary_ties = [row["submission_id"] for row, key in zip(rows, keys) if key == boundary_key]
    return {
        "status": "tie" if len(boundary_ties) > 1 else "ranked",
        "winner_count": winner_count,
        "winner_submission_ids": [row["submission_id"] for row in rows[:winner_count]]
        if len(boundary_ties) == 1
        else [],
        "boundary_tie_submission_ids": boundary_ties if len(boundary_ties) > 1 else [],
        "entries": rows,
    }
