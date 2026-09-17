"""Tests for the trusted, chain level accumulation funnel."""

from __future__ import annotations

import pytest

from harness.schema import SessionRecord
from harness.sequence import score_sequences
from harness.sequence_labels import apply_label_set, load_label_set


def _record(position: int, arm: str = "recall") -> SessionRecord:
    return SessionRecord(
        task_id=f"task-{position}",
        arm=arm,
        seed=0,
        success=True,
        metadata={
            "sequence": {
                "chain_id": "c1",
                "length": 2,
                "position": position,
                "role": "source" if position == 0 else "target",
                "admitted": True,
            },
            "memory_events": [],
        },
    )


def _labels():
    return load_label_set(
        {
            "schema": 2,
            "label_set_id": "labels-1",
            "sequence_plan_id": "plan-1",
            "sequence_plan_digest": "b" * 64,
            "evaluation_manifest_id": "manifest-1",
            "evaluation_manifest_digest": "a" * 64,
            "sessions": [
                {
                    "arm": "recall",
                    "sequence": {"chain_id": "c1", "position": 0},
                    "funnel": {"encountered": True, "retained": True},
                },
                {
                    "arm": "recall",
                    "sequence": {"chain_id": "c1", "position": 1},
                    "funnel": {"retrieved": True, "applied": False},
                },
            ],
        }
    )


def test_funnel_labels_join_to_source_and_target_sessions():
    records = apply_label_set([_record(0), _record(1)], _labels())
    assert records[0].metadata["sequence_funnel"] == {"encountered": True, "retained": True}
    assert records[1].metadata["sequence_funnel"] == {"retrieved": True, "applied": False}

    metrics = score_sequences(records, baseline_arm="recall")["metrics"][0]["funnel"]
    assert metrics["encountered"] == {"observed": 1, "successes": 1, "rate": 1}
    assert metrics["retained"] == {"observed": 1, "successes": 1, "rate": 1}
    assert metrics["retrieved"] == {"observed": 1, "successes": 1, "rate": 1}
    assert metrics["applied"] == {"observed": 1, "successes": 0, "rate": 0}


def test_funnel_labels_must_match_source_or_target_role():
    label_set = load_label_set({**_labels().data, "sessions": [{
        "arm": "recall",
        "sequence": {"chain_id": "c1", "position": 1},
        "funnel": {"encountered": True},
    }]})
    with pytest.raises(ValueError, match="belong on source"):
        apply_label_set([_record(0), _record(1)], label_set)


def test_unlabelled_funnel_stays_unknown():
    records = [_record(0), _record(1)]
    metrics = score_sequences(records, baseline_arm="recall")["metrics"][0]["funnel"]
    assert all(row["observed"] == 0 and row["rate"] is None for row in metrics.values())
