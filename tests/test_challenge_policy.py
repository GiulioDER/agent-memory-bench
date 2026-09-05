"""Tests for the frozen evaluator policy artifact."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.challenge_policy import ChallengePolicyError, load_policy


def _write_policy(path: Path, **overrides) -> Path:
    data = {
        "schema": 1,
        "kind": "amb-challenge-evaluation-policy",
        "policy_id": "policy-a",
        "agent_timeout_seconds": 900,
        "checker_timeout_seconds": 900,
        "adapter_call_budget": 128,
        "model_id": "model-a",
        "provider_id": "provider-a",
        "temperature": 0,
        "context_limit_tokens": 32768,
        "infrastructure_retries": 1,
    }
    data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_policy_loads_and_hashes_canonically(tmp_path: Path):
    first = load_policy(_write_policy(tmp_path / "policy.json"))
    second_path = _write_policy(tmp_path / "policy-2.json")
    second_path.write_text(
        json.dumps(json.loads(second_path.read_text()), indent=2), encoding="utf-8"
    )
    second = load_policy(second_path)
    assert first.to_dict() == second.to_dict()
    assert first.digest() == second.digest()


@pytest.mark.parametrize(
    "overrides",
    [
        {"adapter_call_budget": 0},
        {"agent_timeout_seconds": 0},
        {"temperature": 3},
        {"temperature": "nan"},
        {"agent_timeout_seconds": "inf"},
        {"infrastructure_retries": -1},
    ],
)
def test_policy_rejects_invalid_limits(tmp_path: Path, overrides: dict):
    with pytest.raises(ChallengePolicyError):
        load_policy(_write_policy(tmp_path / "policy.json", **overrides))


def test_policy_frozen_mode_rejects_placeholders(tmp_path: Path):
    with pytest.raises(ChallengePolicyError, match="freeze placeholders"):
        load_policy(
            _write_policy(tmp_path / "policy.json", model_id="TO_BE_FROZEN"),
            require_frozen=True,
        )
