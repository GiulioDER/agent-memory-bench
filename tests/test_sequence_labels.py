"""Tests for post run, externally supplied sequence event labels."""

from __future__ import annotations

import json
import sys

import pytest

from harness.io import write_jsonl
from harness.schema import SessionRecord
from harness.sequence_labels import apply_label_set, load_label_set
from harness.sequence_plan import load_plan
from scripts.score_sequence import main


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
            "schema": 2,
            "label_set_id": "labels-1",
            "sequence_plan_id": "sequence-1",
            "sequence_plan_digest": "b" * 64,
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


def test_label_set_requires_the_bound_plan_digest():
    data = dict(_label_set().data)
    data.pop("sequence_plan_digest")
    with pytest.raises(ValueError, match="sequence_plan_digest"):
        load_label_set(data)


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


def test_score_command_applies_matching_bound_labels(tmp_path, monkeypatch):
    records = []
    for arm in ("bare", "recall"):
        for position in (0, 1):
            events = []
            if arm == "recall" and position == 0:
                events.append(
                    {
                        "kind": "retrieve",
                        "decision": "retrieve",
                        "source": "tool_calls[0].mcp__memory__search",
                    }
                )
            records.append(
                SessionRecord(
                    task_id=f"task-{position}",
                    arm=arm,
                    seed=0,
                    success=True,
                    metadata={
                        "sequence": {
                            "chain_id": "c1",
                            "length": 2,
                            "position": position,
                            "role": "target" if position else "source",
                            "admitted": True,
                        },
                        "memory_events": events,
                    },
                )
            )
    records_path = tmp_path / "records.jsonl"
    write_jsonl(records_path, records)
    plan_path = tmp_path / "plan.json"
    plan_data = {
        "schema": 1,
        "plan_id": "sequence-1",
        "evaluation_manifest_id": "manifest-1",
        "evaluation_manifest_digest": "a" * 64,
        "baseline_arm": "bare",
        "arms": ["bare", "recall"],
        "chains": [
            {
                "chain_id": "c1",
                "seed": 0,
                "sessions": [
                    {
                        "task_id": "task-0",
                        "position": 0,
                        "role": "source",
                        "user_input": "learn",
                    },
                    {
                        "task_id": "task-1",
                        "position": 1,
                        "role": "target",
                        "user_input": "apply",
                    },
                ],
            }
        ],
    }
    plan_path.write_text(
        json.dumps(plan_data),
        encoding="utf-8",
    )
    labels_path = tmp_path / "labels.json"
    labels = dict(_label_set().data)
    labels["schema"] = 2
    labels["sequence_plan_digest"] = load_plan(plan_data).digest
    labels_path.write_text(json.dumps(labels), encoding="utf-8")
    out_dir = tmp_path / "analysis"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "score_sequence",
            str(records_path),
            "--out-dir",
            str(out_dir),
            "--oracle-labels",
            str(labels_path),
            "--sequence-plan",
            str(plan_path),
        ],
    )
    assert main() == 0
    analysis = json.loads((out_dir / "sequence_analysis.json").read_text(encoding="utf-8"))
    recall = next(row for row in analysis["metrics"] if row["arm"] == "recall")
    assert recall["selectivity"]["retrieval_precision"] == 1
