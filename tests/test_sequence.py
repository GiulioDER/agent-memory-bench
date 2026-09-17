"""Tests for sequence level outcomes, selectivity, and overhead accounting."""

from __future__ import annotations

import pytest

from harness.schema import SessionRecord
from harness.sequence import score_sequences
from scripts.score_sequence import render_markdown


def _record(
    chain: str,
    arm: str,
    position: int,
    *,
    length: int = 2,
    success: bool = True,
    admitted: bool = True,
    role: str | None = None,
    events=(),
    input_tokens: int | None = 10,
    output_tokens: int | None = 2,
    memory_input_tokens: int | None = 1,
    memory_output_tokens: int | None = 1,
) -> SessionRecord:
    return SessionRecord(
        task_id=f"task-{chain}-{position}",
        arm=arm,
        seed=0,
        success=success,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        metadata={
            "sequence": {
                "chain_id": chain,
                "length": length,
                "position": position,
                "role": role or ("target" if position == length - 1 else "source"),
                "admitted": admitted,
            },
            "memory_events": list(events),
            "memory_input_tokens": memory_input_tokens,
            "memory_output_tokens": memory_output_tokens,
            "memory_storage_bytes": 4,
        },
    )


def test_sequence_scores_target_success_and_chain_overhead():
    records = [
        _record("c1", "bare", 0),
        _record("c1", "bare", 1),
        _record("c1", "recall", 0, events=({"kind": "write", "decision": "write", "useful": True},)),
        _record("c1", "recall", 1, success=False, events=({"kind": "retrieve", "decision": "retrieve", "useful": False, "harmful": True},)),
    ]
    result = score_sequences(records)
    recall = next(row for row in result["metrics"] if row["arm"] == "recall")
    assert recall["target_success_rate"] == 0
    assert recall["paired_harm_rate"] == 1
    assert recall["overhead"]["total_tokens"] == 24
    assert recall["overhead"]["mean_total_token_delta_vs_baseline"] == 0
    assert recall["selectivity"]["write_precision"] == 1
    assert recall["selectivity"]["retrieval_precision"] == 0
    assert recall["selectivity"]["retrieval_abstention_rate"] == 0
    assert recall["selectivity"]["retrieval_harm_rate"] == 1


def test_unadmitted_chain_is_not_scored():
    """Mutation: dropping the admitted filter would turn a refused partial chain into evidence."""

    records = [
        _record("c1", "bare", 0),
        _record("c1", "bare", 1, admitted=False),
        _record("c1", "recall", 0),
        _record("c1", "recall", 1),
    ]
    result = score_sequences(records)
    admitted = {row["arm"]: row["admitted_chains"] for row in result["metrics"]}
    assert admitted == {"bare": 0, "recall": 1}


def test_duplicate_position_is_refused():
    """Mutation: removing the duplicate guard would count a retry as a second chain session."""

    records = [
        _record("c1", "bare", 0),
        _record("c1", "bare", 0),
        _record("c1", "bare", 1),
        _record("c1", "recall", 0),
        _record("c1", "recall", 1),
    ]
    with pytest.raises(ValueError, match="appears more than once"):
        score_sequences(records)


def test_missing_sequence_contract_is_refused():
    record = _record("c1", "bare", 0).to_dict()
    record["metadata"] = {}
    with pytest.raises(ValueError, match="requires metadata.sequence"):
        score_sequences([record])


def test_unlabelled_selectivity_remains_unknown():
    records = [
        _record("c1", "bare", 0),
        _record("c1", "bare", 1),
        _record("c1", "recall", 0, events=({"kind": "write", "decision": "write"},)),
        _record("c1", "recall", 1, events=({"kind": "retrieve", "decision": "abstain"},)),
    ]
    recall = next(row for row in score_sequences(records)["metrics"] if row["arm"] == "recall")
    assert recall["selectivity"]["write_precision"] is None
    assert recall["selectivity"]["retrieval_precision"] is None
    assert recall["selectivity"]["retrieval_abstention_rate"] == 1


def test_sequence_markdown_renderer_formats_scored_rows():
    records = [
        _record("c1", "bare", 0),
        _record("c1", "bare", 1),
        _record("c1", "recall", 0),
        _record("c1", "recall", 1),
    ]
    markdown = render_markdown(score_sequences(records))
    assert "# Sequence and Selectivity Analysis" in markdown
    assert "| recall | 2 | 1 | 1.000 | 1.000 | 0.000 |" in markdown
