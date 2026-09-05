"""Validate and hash the contest rules used for a prize release."""

from __future__ import annotations

import hashlib
import json
import math
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
        "independent_reviewer_count",
        "sponsor_entry_eligible",
        "infrastructure_retry_count",
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
    numeric_positive = ("prize_total_usd", "winner_count", "appeal_window_days", "independent_reviewer_count")
    for field in numeric_positive:
        value = data[field]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ChallengeRulesError(f"rules field {field!r} must be positive")
    if not isinstance(data["infrastructure_retry_count"], int) or data["infrastructure_retry_count"] < 0:
        raise ChallengeRulesError("infrastructure_retry_count must be non negative")
    if data["sponsor_entry_eligible"] is not False:
        raise ChallengeRulesError("sponsor_entry_eligible must be false")
    if not isinstance(data["tie_breaker_task_ids"], list) or not all(
        isinstance(task_id, str) and task_id.strip() for task_id in data["tie_breaker_task_ids"]
    ):
        raise ChallengeRulesError("tie_breaker_task_ids must be a list of non empty strings")
    if not isinstance(data["publication"], dict):
        raise ChallengeRulesError("publication must be an object")
    if any(not isinstance(value, bool) for value in data["publication"].values()):
        raise ChallengeRulesError("publication values must be booleans")
    if require_final:
        if data["status"] != "final":
            raise ChallengeRulesError("final release requires status='final' rules")
        if "TO_BE_" in json.dumps(data, sort_keys=True):
            raise ChallengeRulesError("final rules contain unresolved approval placeholders")
        if not data["tie_breaker_task_ids"]:
            raise ChallengeRulesError("final rules need at least one tie breaker task")
    return data


def rules_digest(rules: dict[str, Any]) -> str:
    canonical = json.dumps(rules, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
