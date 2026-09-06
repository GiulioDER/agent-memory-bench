"""Load and hash the evaluator policy that must remain fixed across submissions."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

POLICY_SCHEMA = 1
POLICY_KIND = "amb-challenge-evaluation-policy"
SHA256 = re.compile(r"^[0-9a-f]{64}$")

MAX_AGENT_TIMEOUT_SECONDS = 3600.0
MAX_CHECKER_TIMEOUT_SECONDS = 3600.0
MAX_ADAPTER_CALL_BUDGET = 10_000
MAX_CONTEXT_LIMIT_TOKENS = 131_072
MAX_INFRASTRUCTURE_RETRIES = 3


class ChallengePolicyError(ValueError):
    """The evaluator policy is missing, malformed or unsafe to use."""


@dataclass(frozen=True)
class ChallengeEvaluationPolicy:
    policy_id: str
    agent_command_sha256: str
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
        if not self.agent_command_sha256.startswith("TO_BE_") and not SHA256.fullmatch(
            self.agent_command_sha256
        ):
            raise ChallengePolicyError("agent_command_sha256 must be a lowercase SHA256 digest")
        if (
            not math.isfinite(self.agent_timeout_seconds)
            or not math.isfinite(self.checker_timeout_seconds)
            or self.agent_timeout_seconds <= 0
            or self.checker_timeout_seconds <= 0
            or self.agent_timeout_seconds > MAX_AGENT_TIMEOUT_SECONDS
            or self.checker_timeout_seconds > MAX_CHECKER_TIMEOUT_SECONDS
        ):
            raise ChallengePolicyError(
                "policy timeouts must be positive and at most one hour"
            )
        if (
            isinstance(self.adapter_call_budget, bool)
            or not isinstance(self.adapter_call_budget, int)
            or isinstance(self.context_limit_tokens, bool)
            or not isinstance(self.context_limit_tokens, int)
        ):
            raise ChallengePolicyError("policy budgets must be integers")
        if (
            self.adapter_call_budget <= 0
            or self.adapter_call_budget > MAX_ADAPTER_CALL_BUDGET
            or self.context_limit_tokens <= 0
            or self.context_limit_tokens > MAX_CONTEXT_LIMIT_TOKENS
        ):
            raise ChallengePolicyError("policy budgets exceed the evaluator limits")
        if not math.isfinite(self.temperature) or not 0 <= self.temperature <= 2:
            raise ChallengePolicyError("policy temperature must be between 0 and 2")
        if (
            isinstance(self.infrastructure_retries, bool)
            or not isinstance(self.infrastructure_retries, int)
            or self.infrastructure_retries < 0
            or self.infrastructure_retries > MAX_INFRASTRUCTURE_RETRIES
        ):
            raise ChallengePolicyError("infrastructure retries must be between 0 and 3")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": POLICY_SCHEMA,
            "kind": POLICY_KIND,
            "policy_id": self.policy_id,
            "agent_command_sha256": self.agent_command_sha256,
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


def agent_command_digest(command: Sequence[str]) -> str:
    """Hash the canonical argv used to launch the evaluator owned fixed agent."""

    if not command or any(not isinstance(part, str) or not part for part in command):
        raise ChallengePolicyError("agent command must be a non empty argument list")
    canonical = json.dumps(list(command), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_policy(path: str | Path, *, require_frozen: bool = False) -> ChallengeEvaluationPolicy:
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
    if (
        type(data.get("schema")) is not int
        or data["schema"] != POLICY_SCHEMA
        or data.get("kind") != POLICY_KIND
    ):
        raise ChallengePolicyError("unsupported challenge policy")
    try:
        policy = ChallengeEvaluationPolicy(
            policy_id=_string(data, "policy_id"),
            agent_command_sha256=_digest(data, "agent_command_sha256"),
            agent_timeout_seconds=_positive_float(data, "agent_timeout_seconds"),
            checker_timeout_seconds=_positive_float(data, "checker_timeout_seconds"),
            adapter_call_budget=_positive_int(data, "adapter_call_budget"),
            model_id=_string(data, "model_id"),
            provider_id=_string(data, "provider_id"),
            temperature=_number(data, "temperature"),
            context_limit_tokens=_positive_int(data, "context_limit_tokens"),
            infrastructure_retries=_nonnegative_int(data, "infrastructure_retries"),
        )
        if require_frozen and any(
            "TO_BE_" in value
            for value in (
                policy.policy_id,
                policy.agent_command_sha256,
                policy.model_id,
                policy.provider_id,
            )
        ):
            raise ChallengePolicyError("policy contains unresolved freeze placeholders")
        return policy
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


def _digest(data: dict[str, Any], field: str) -> str:
    value = _string(data, field)
    if value.startswith("TO_BE_"):
        return value
    value = value.lower()
    if not SHA256.fullmatch(value):
        raise ChallengePolicyError(f"policy field {field!r} must be a lowercase SHA256 digest")
    return value


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
