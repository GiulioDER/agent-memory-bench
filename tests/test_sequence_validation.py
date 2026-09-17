"""Tests for preflight validation of executable longitudinal plans."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.sequence_plan import load_plan
from harness.sequence_validation import validate_plan


def _plan(source: str = "ts-atomic-write", target: str = "ts-bool-env", length: int = 2):
    def prompt(task_id: str) -> str:
        return json.loads((Path("tasks") / task_id / "task.json").read_text())["prompt"]

    sessions = [
        {
            "task_id": source,
            "position": 0,
            "role": "source",
            "user_input": prompt(source),
        }
    ]
    for position in range(1, length - 1):
        task_id = "ts-empty-input"
        sessions.append(
            {
                "task_id": task_id,
                "position": position,
                "role": "distance",
                "user_input": prompt(task_id),
            }
        )
    target_prompt = prompt(target)
    sessions.append(
        {"task_id": target, "position": length - 1, "role": "target", "user_input": target_prompt}
    )
    return load_plan(
        {
            "schema": 1,
            "plan_id": "validation-test",
            "evaluation_manifest_id": "manifest",
            "evaluation_manifest_digest": "a" * 64,
            "baseline_arm": "bare",
            "arms": ["bare", "recall"],
            "chains": [{"chain_id": "c1", "seed": 0, "sessions": sessions}],
        }
    )


def test_plan_binds_real_primary_tasks_and_reports_dimensions():
    result = validate_plan(_plan(), tasks_root="tasks")
    assert result.to_dict() == {
        "plan_id": "validation-test",
        "chains": 1,
        "chains_by_length": {2: 1},
        "task_ids": ["ts-atomic-write", "ts-bool-env"],
    }


def test_plan_refuses_prompt_drift():
    plan = _plan()
    data = dict(plan.data)
    data["chains"] = [{**data["chains"][0], "sessions": [
        {**data["chains"][0]["sessions"][0], "user_input": "changed"},
        data["chains"][0]["sessions"][1],
    ]}]
    with pytest.raises(ValueError, match="does not match"):
        validate_plan(load_plan(data), tasks_root="tasks")


def test_plan_refuses_source_fact_in_shared_instructions(tmp_path):
    shared = tmp_path / "shared.md"
    shared.write_text("always use an atomic write", encoding="utf-8")
    with pytest.raises(ValueError, match="shared instructions"):
        validate_plan(_plan(), tasks_root="tasks", shared_files=[shared])


def test_plan_refuses_unapproved_length():
    with pytest.raises(ValueError, match="allowed lengths"):
        validate_plan(_plan(length=3), tasks_root="tasks")


def test_plan_can_enforce_the_preregistered_chain_count():
    with pytest.raises(ValueError, match="length 2 has 1 chain"):
        validate_plan(_plan(), tasks_root="tasks", expected_chains_per_length=12)
