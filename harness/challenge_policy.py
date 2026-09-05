"""Load and hash the evaluator policy that must remain fixed across submissions."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

POLICY_SCHEMA = 1
POLICY_KIND = "amb-challenge-evaluation-policy"


class ChallengePolicyError(ValueError):
    """The evaluator policy is missing, malformed or unsafe to use."""


@dataclass(frozen=True)
class ChallengeEvaluationPolicy:
    policy_id: str
    agent_timeout_seconds: float
    checker_timeout_seconds: float
    adapter_call_budget: int
    model_id: str
    provider_id: str
    temperature: float
    context_limit_tokens: int
    infrastructure_retries: int

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or not self.model_id.strip() or not self.provider_id.strip():
            raise ChallengePolicyError("policy identifiers must be non empty")
        if (
            not math.isfinite(self.agent_timeout_seconds)
            or not math.isfinite(self.checker_timeout_seconds)
            or self.agent_timeout_seconds <= 0
            or self.checker_timeout_seconds <= 0
        ):
            raise ChallengePolicyError("policy timeouts must be positive")
        if self.adapter_call_budget <= 0 or self.context_limit_tokens <= 0:
            raise ChallengePolicyError("policy budgets must be positive")
        if not math.isfinite(self.temperature) or not 0 <= self.temperature <= 2:
            raise ChallengePolicyError("policy temperature must be between 0 and 2")
        if self.infrastructure_retries < 0:
            raise ChallengePolicyError("infrastructure retries cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": POLICY_SCHEMA,
            "kind": POLICY_KIND,
            "policy_id": self.policy_id,
            "agent_timeout_seconds": self.agent_timeout_seconds,
            "checker_timeout_seconds": self.checker_timeout_seconds,
            "adapter_call_budget": self.adapter_call_budget,
            "model_id": self.model_id,
            "provider_id": self.provider_id,
            "temperature": self.temperature,
            "context_limit_tokens": self.context_limit_tokens,
            "infrastructure_retries": self.infrastructure_retries,
        }

    def digest(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(canonical).hexdigest()


def load_policy(path: str | Path) -> ChallengeEvaluationPolicy:
    """Load one immutable policy file without following a symlink at its target."""

    raw_path = Path(path).expanduser()
    if raw_path.is_symlink() or not raw_path.is_file():
        raise ChallengePolicyError(f"policy is not a regular file: {raw_path}")
    try:
        data = json.loads(raw_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ChallengePolicyError(f"cannot read policy: {raw_path}") from error
    if not isinstance(data, dict):
        raise ChallengePolicyError("policy must contain an object")
    if data.get("schema") != POLICY_SCHEMA or data.get("kind") != POLICY_KIND:
        raise ChallengePolicyError("unsupported challenge policy")
    try:
        return ChallengeEvaluationPolicy(
            policy_id=_string(data, "policy_id"),
            agent_timeout_seconds=_positive_float(data, "agent_timeout_seconds"),
            checker_timeout_seconds=_positive_float(data, "checker_timeout_seconds"),
            adapter_call_budget=_positive_int(data, "adapter_call_budget"),
            model_id=_string(data, "model_id"),
            provider_id=_string(data, "provider_id"),
            temperature=_number(data, "temperature"),
            context_limit_tokens=_positive_int(data, "context_limit_tokens"),
            infrastructure_retries=_nonnegative_int(data, "infrastructure_retries"),
        )
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, ChallengePolicyError):
            raise
        raise ChallengePolicyError(f"invalid challenge policy: {error}") from error


def _string(data: dict[str, Any], field: str) -> str:
    value = data[field]
    if not isinstance(value, str) or not value.strip():
        raise ChallengePolicyError(f"policy field {field!r} must be a non empty string")
    return value


def _number(data: dict[str, Any], field: str) -> float:
    value = data[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ChallengePolicyError(f"policy field {field!r} must be a number")
    return float(value)


def _positive_float(data: dict[str, Any], field: str) -> float:
    value = _number(data, field)
    if not math.isfinite(value) or value <= 0:
        raise ChallengePolicyError(f"policy field {field!r} must be positive")
    return value


def _positive_int(data: dict[str, Any], field: str) -> int:
    value = data[field]
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ChallengePolicyError(f"policy field {field!r} must be a positive integer")
    return value


def _nonnegative_int(data: dict[str, Any], field: str) -> int:
    value = data[field]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ChallengePolicyError(f"policy field {field!r} must be a non negative integer")
    return value
