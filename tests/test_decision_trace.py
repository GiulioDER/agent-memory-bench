from __future__ import annotations

from harness.claude_exec import parse_claude_stream_json, transcript_fields
from harness.decision_trace import evaluate_decisions, evaluate_record
from harness.schema import SessionRecord


def test_low_confidence_answer_fails_the_observed_contract() -> None:
    result = evaluate_decisions(
        [{"decision": "answer", "confidence": 0.31, "threshold": 0.5, "source": "memory"}]
    )
    assert result["status"] == "fail"
    assert result["observed_decision"] is True
    assert result["calibration"]["status"] == "not_evaluated"


def test_low_confidence_abstain_passes_but_does_not_certify_calibration() -> None:
    result = evaluate_decisions(
        [{
            "decision": "abstain",
            "confidence": 0.31,
            "threshold": 0.5,
            "source": "memory",
        }]
    )
    assert result["status"] == "pass"
    assert result["abstention_observed"] is True
    assert result["calibration"]["status"] == "not_evaluated"


def test_final_response_words_do_not_count_without_a_runtime_event() -> None:
    result = evaluate_record(
        {
            "response": "I could not find any record of the convention.",
            "tool_calls": [],
        }
    )
    assert result["status"] == "not_observed"
    assert result["abstention_observed"] is False


def test_explicit_decision_in_a_memory_tool_result_is_replayed() -> None:
    result = evaluate_record(
        {
            "response": "I will answer.",
            "tool_calls": [
                {
                    "name": "mcp__recall__recall_search",
                    "output": '{"bundle":{"decision":"escalate","confidence":0.2}}',
                }
            ],
        },
        threshold=0.5,
    )
    assert result["status"] == "pass"
    assert result["decisions"][0]["decision"] == "escalate"


def test_runtime_decision_survives_the_session_record_round_trip() -> None:
    record = SessionRecord(
        task_id="t1",
        arm="recall",
        success=True,
        runtime_decisions=(
            {
                "decision": "abstain",
                "source": "runtime",
                "confidence": 0.2,
                "threshold": 0.5,
            },
        ),
    )
    restored = SessionRecord.from_mapping(record.to_dict())
    assert restored.runtime_decisions == record.runtime_decisions
    assert evaluate_record(restored.to_dict())["abstention_observed"] is True


def test_claude_transcript_persists_explicit_runtime_decision() -> None:
    stream = (
        '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"1",'
        '"name":"mcp__recall__recall_search","input":{}}]}}\n'
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"1",'
        '"content":"{\\"decision\\":\\"abstain\\",\\"confidence\\":0.1,'
        '\\"threshold\\":0.5}"}]}}\n'
        '{"type":"result","result":"I cannot answer."}'
    )
    fields = transcript_fields(parse_claude_stream_json(stream))
    assert fields.runtime_decisions == (
        {
            "decision": "abstain",
            "source": "tool_calls[0].output:mcp__recall__recall_search",
            "confidence": 0.1,
            "threshold": 0.5,
            "reason": None,
        },
    )
