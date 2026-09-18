"""Tests for sequence level work accounting and paired efficiency deltas."""

from __future__ import annotations

from harness.schema import SessionRecord
from harness.sequence import score_sequences
from scripts.score_sequence import render_markdown


def _record(arm: str, position: int, *, tools: int, wall: float) -> SessionRecord:
    return SessionRecord(
        task_id=f"task-{position}",
        arm=arm,
        seed=0,
        success=True,
        wall_time_ms=wall,
        tool_calls=tuple({"name": f"tool-{index}"} for index in range(tools)),
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


def test_sequence_reports_work_and_paired_efficiency_deltas():
    records = [
        _record("bare", 0, tools=4, wall=100),
        _record("bare", 1, tools=6, wall=140),
        _record("recall", 0, tools=3, wall=80),
        _record("recall", 1, tools=2, wall=90),
    ]
    rows = score_sequences(records)["metrics"]
    recall = next(row for row in rows if row["arm"] == "recall")
    overhead = recall["overhead"]
    assert overhead["tool_calls"] == 5
    assert overhead["wall_time_ms"] == 170
    assert overhead["mean_tool_call_delta_vs_baseline"] == -5
    assert overhead["mean_wall_time_delta_vs_baseline"] == -70
    assert overhead["tool_call_delta_pairs"] == 1
    assert overhead["wall_time_delta_pairs"] == 1


def test_missing_work_measurements_remain_unknown():
    record = _record("bare", 0, tools=1, wall=20).to_dict()
    record.pop("tool_calls")
    record["wall_time_ms"] = None
    record["metadata"]["sequence"]["position"] = 0
    record2 = _record("bare", 1, tools=1, wall=20).to_dict()
    record2.pop("tool_calls")
    record2["wall_time_ms"] = None
    result = score_sequences([record, record2], baseline_arm="bare")
    overhead = result["metrics"][0]["overhead"]
    assert overhead["tool_calls"] is None
    assert overhead["wall_time_ms"] is None


def test_sequence_report_exposes_all_work_saved_measurements():
    records = [
        _record("bare", 0, tools=4, wall=100),
        _record("bare", 1, tools=6, wall=140),
        _record("recall", 0, tools=3, wall=80),
        _record("recall", 1, tools=2, wall=90),
    ]
    markdown = render_markdown(score_sequences(records))
    assert "Tool calls" in markdown
    assert "Tool-call delta vs baseline" in markdown
    assert "Wall time (ms)" in markdown
    assert "Wall-time delta vs baseline" in markdown
    assert "| recall | 2 | unknown | unknown | unknown | unknown | unknown | unknown | unknown | unknown | unknown | 5 | -5.0 | 170 | -70.0 |" in markdown
