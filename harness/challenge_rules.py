"""Validate and hash the contest rules used for a prize release."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

RULES_SCHEMA = 1
RULES_KIND = "amb-challenge-rules"


class ChallengeRulesError(ValueError):
    """The contest rules are missing, malformed or not approved for release."""


def load_rules(path: str | Path, *, require_final: bool = False) -> dict[str, Any]:
    raw_path = Path(path).expanduser()
    if raw_path.is_symlink() or not raw_path.is_file():
        raise ChallengeRulesError(f"rules are not a regular file: {raw_path}")
    try:
        data = json.loads(raw_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ChallengeRulesError(f"cannot read rules: {raw_path}") from error
    if not isinstance(data, dict):
        raise ChallengeRulesError("rules must contain an object")
    if data.get("schema") != RULES_SCHEMA or data.get("kind") != RULES_KIND:
        raise ChallengeRulesError("unsupported challenge rules")
    required = (
        "rules_id",
        "status",
        "prize_total_usd",
        "winner_count",
        "appeal_window_days",
        "entry_deadline_utc",
        "tie_breaker_task_ids",
        "excluded_submission_ids",
        "independent_reviewer_count",
        "sponsor_entry_eligible",
        "infrastructure_retry_count",
        "baseline_minimum_margin",
        "appeal_scope",
        "publication",
    )
    missing = [field for field in required if field not in data]
    if missing:
        raise ChallengeRulesError(f"rules missing fields: {', '.join(missing)}")
    if not isinstance(data["rules_id"], str) or not data["rules_id"].strip():
        raise ChallengeRulesError("rules_id must be a non empty string")
    if data["status"] not in {"draft", "final"}:
        raise ChallengeRulesError("rules status must be draft or final")
    if not isinstance(data["entry_deadline_utc"], str) or not data["entry_deadline_utc"].strip():
        raise ChallengeRulesError("entry_deadline_utc must be a non empty string")
    if not isinstance(data["appeal_scope"], str) or not data["appeal_scope"].strip():
        raise ChallengeRulesError("appeal_scope must be a non empty string")
    prize_total_usd = data["prize_total_usd"]
    if (
        isinstance(prize_total_usd, bool)
        or not isinstance(prize_total_usd, (int, float))
        or not math.isfinite(prize_total_usd)
        or prize_total_usd <= 0
    ):
        raise ChallengeRulesError("rules field 'prize_total_usd' must be a positive finite number")
    for field in ("winner_count", "appeal_window_days", "independent_reviewer_count"):
        value = data[field]
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
        ):
            raise ChallengeRulesError(f"rules field {field!r} must be a positive integer")
    if not isinstance(data["infrastructure_retry_count"], int) or data["infrastructure_retry_count"] < 0:
        raise ChallengeRulesError("infrastructure_retry_count must be non negative")
    baseline_minimum_margin = data["baseline_minimum_margin"]
    if (
        isinstance(baseline_minimum_margin, bool)
        or not isinstance(baseline_minimum_margin, (int, float))
        or not math.isfinite(baseline_minimum_margin)
        or not 0 < baseline_minimum_margin <= 1
    ):
        raise ChallengeRulesError(
            "baseline_minimum_margin must be a positive finite number at most 1"
        )
    if data["sponsor_entry_eligible"] is not False:
        raise ChallengeRulesError("sponsor_entry_eligible must be false")
    if not isinstance(data["tie_breaker_task_ids"], list) or not all(
        isinstance(task_id, str) and task_id.strip() for task_id in data["tie_breaker_task_ids"]
    ):
        raise ChallengeRulesError("tie_breaker_task_ids must be a list of non empty strings")
    if len(set(data["tie_breaker_task_ids"])) != len(data["tie_breaker_task_ids"]):
        raise ChallengeRulesError("tie_breaker_task_ids must not contain duplicates")
    if not isinstance(data["excluded_submission_ids"], list) or not all(
        isinstance(submission_id, str) and submission_id.strip()
        for submission_id in data["excluded_submission_ids"]
    ):
        raise ChallengeRulesError("excluded_submission_ids must be a list of non empty strings")
    if len(set(data["excluded_submission_ids"])) != len(data["excluded_submission_ids"]):
        raise ChallengeRulesError("excluded_submission_ids must not contain duplicates")
    if not isinstance(data["publication"], dict):
        raise ChallengeRulesError("publication must be an object")
    if any(not isinstance(value, bool) for value in data["publication"].values()):
        raise ChallengeRulesError("publication values must be booleans")
    if require_final:
        if data["status"] != "final":
            raise ChallengeRulesError("final release requires status='final' rules")
        if "TO_BE_" in json.dumps(data, sort_keys=True):
            raise ChallengeRulesError("final rules contain unresolved approval placeholders")
        if data["independent_reviewer_count"] != 1:
            raise ChallengeRulesError(
                "final release format supports exactly one independent roster reviewer"
            )
        if not data["tie_breaker_task_ids"]:
            raise ChallengeRulesError("final rules need at least one tie breaker task")
        if not data["excluded_submission_ids"]:
            raise ChallengeRulesError("final rules need at least one excluded submission id")
        deadline = data["entry_deadline_utc"]
        try:
            parsed_deadline = datetime.fromisoformat(deadline)
        except ValueError as error:
            raise ChallengeRulesError("final rules entry_deadline_utc must be an ISO 8601 UTC timestamp") from error
        if parsed_deadline.tzinfo is None or parsed_deadline.utcoffset() != timedelta(0):
            raise ChallengeRulesError("final rules entry_deadline_utc must include UTC timezone")
    return data


def rules_digest(rules: dict[str, Any]) -> str:
    canonical = json.dumps(rules, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_rules_for_task_ids(rules: dict[str, Any], task_ids: Iterable[str]) -> None:
    """Reject tie breaker rules that cannot refer to a private task."""

    known_task_ids = set(task_ids)
    unknown = sorted(set(rules["tie_breaker_task_ids"]) - known_task_ids)
    if unknown:
        raise ChallengeRulesError(f"final rules name unknown tie breaker task(s): {unknown}")
