"""Tests for post run, externally supplied sequence event labels."""

from __future__ import annotations

import pytest

from harness.schema import SessionRecord
from harness.sequence_labels import apply_label_set, load_label_set


def _record() -> SessionRecord:
    return SessionRecord(
        task_id="source",
        arm="recall",
        seed=0,
        success=True,
        metadata={
            "sequence": {
                "chain_id": "c1",
                "length": 2,
                "position": 0,
                "role": "source",
                "admitted": True,
            },
            "memory_events": [
                {
                    "kind": "retrieve",
                    "decision": "retrieve",
                    "source": "tool_calls[0].mcp__memory__search",
                }
            ],
        },
    )


def _label_set():
    return load_label_set(
        {
            "schema": 1,
            "label_set_id": "labels-1",
            "sequence_plan_id": "sequence-1",
            "evaluation_manifest_id": "manifest-1",
            "evaluation_manifest_digest": "a" * 64,
            "sessions": [
                {
                    "arm": "recall",
                    "sequence": {"chain_id": "c1", "position": 0},
                    "events": [
                        {
                            "source": "tool_calls[0].mcp__memory__search",
                            "useful": True,
                            "harmful": False,
                            "applied": True,
                        }
                    ],
                }
            ],
        }
    )


def test_label_set_joins_labels_to_observed_events_only():
    labelled = apply_label_set([_record()], _label_set())
    event = labelled[0].metadata["memory_events"][0]
    assert event["useful"] is True
    assert event["harmful"] is False
    assert event["applied"] is True


def test_label_set_refuses_a_session_absent_from_records():
    with pytest.raises(ValueError, match="absent record sessions"):
        apply_label_set([], _label_set())


def test_label_set_rejects_unknown_event_sources():
    label_set = load_label_set(
        {
            **_label_set().data,
            "sessions": [
                {
                    "arm": "recall",
                    "sequence": {"chain_id": "c1", "position": 0},
                    "events": [{"source": "missing", "useful": True}],
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="unknown event sources"):
        apply_label_set([_record()], label_set)
