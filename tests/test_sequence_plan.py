"""Tests for the strict sequential chain plan contract."""

from __future__ import annotations

import pytest

from harness.sequence_plan import load_plan


def _plan():
    return {
        "schema": 1,
        "plan_id": "sequence-test",
        "evaluation_manifest_id": "heldout-test",
        "evaluation_manifest_digest": "a" * 64,
        "baseline_arm": "bare",
        "arms": ["bare", "recall"],
        "chains": [
            {
                "chain_id": "c1",
                "seed": 0,
                "sessions": [
                    {"task_id": "source", "position": 0, "role": "source", "user_input": "learn"},
                    {"task_id": "target", "position": 1, "role": "target", "user_input": "apply"},
                ],
            }
        ],
    }


def test_plan_expands_rows_with_runner_owned_sequence_identity():
    rows = load_plan(_plan()).rows()
    assert [row["task_id"] for row in rows] == ["source", "target"]
    assert rows[0]["sequence"] == {
        "chain_id": "c1",
        "length": 2,
        "position": 0,
        "role": "source",
        "admitted": True,
    }


def test_plan_requires_source_then_target_and_distance_middle():
    data = _plan()
    data["chains"][0]["sessions"][0]["role"] = "target"
    with pytest.raises(ValueError, match="start with source"):
        load_plan(data)


def test_plan_requires_a_manifest_binding():
    data = _plan()
    data.pop("evaluation_manifest_digest")
    with pytest.raises(ValueError, match="evaluation_manifest_digest"):
        load_plan(data)


def test_plan_rejects_duplicate_task_within_chain():
    data = _plan()
    data["chains"][0]["sessions"][1]["task_id"] = "source"
    with pytest.raises(ValueError, match="distinct task"):
        load_plan(data)


def test_plan_rejects_position_gaps():
    data = _plan()
    data["chains"][0]["sessions"].insert(
        1,
        {"task_id": "distance", "position": 2, "role": "distance", "user_input": "wait"},
    )
    with pytest.raises(ValueError, match="positions must be ordered"):
        load_plan(data)


def test_plan_rejects_task_seed_reuse_across_chains():
    data = _plan()
    data["chains"].append(
        {
            "chain_id": "c2",
            "seed": 0,
            "sessions": [
                {"task_id": "source", "position": 0, "role": "source", "user_input": "learn"},
                {"task_id": "target-2", "position": 1, "role": "target", "user_input": "apply"},
            ],
        }
    )
    with pytest.raises(ValueError, match="reuses task 'source' at seed 0"):
        load_plan(data)
