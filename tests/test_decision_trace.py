from __future__ import annotations

import json

from harness.claude_exec import parse_claude_stream_json, transcript_fields
from harness.decision_trace import (
    DECISION_OUTPUT_SCHEMA,
    DECISION_STAGE_INSTRUCTION,
    evaluate_decisions,
    evaluate_record,
    with_decision_output_instruction,
)
from harness.schema import SessionRecord


def test_low_confidence_answer_fails_the_observed_contract() -> None:
    result = evaluate_decisions(
        [{"decision": "answer", "confidence": 0.31, "threshold": 0.5, "source": "memory"}]
    )
    assert result["status"] == "fail"
    assert result["observed_decision"] is True
    assert result["n_confidence_scores"] == 1
    assert result["n_confidence_threshold_pairs"] == 1
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
        memory_calls_attempted=2,
        memory_calls_succeeded=1,
        memory_calls_failed=1,
        memory_search_abstained=1,
        memory_hits_returned=3,
        memory_trust_states=("trusted",),
        memory_error_codes=("timeout",),
    )
    restored = SessionRecord.from_mapping(record.to_dict())
    assert restored.runtime_decisions == record.runtime_decisions
    assert restored.memory_calls_attempted == 2
    assert restored.memory_calls_failed == 1
    assert restored.memory_trust_states == ("trusted",)
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


def test_schema_constrained_result_is_recorded_as_a_runtime_decision() -> None:
    stream = (
        '{"type":"result","structured_output":'
        '{"decision":"answer","confidence":0.87,"reason":"checked the generated files"}}'
    )
    fields = transcript_fields(parse_claude_stream_json(stream))
    assert fields.runtime_decisions == (
        {
            "decision": "answer",
            "source": "result.structured_output",
            "confidence": 0.87,
            "threshold": None,
            "reason": "checked the generated files",
        },
    )


def test_structured_output_tool_input_preserves_decision_stage() -> None:
    stream = (
        '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"1",'
        '"name":"StructuredOutput","input":{"decision":"abstain","confidence":0.2,'
        '"stage":"pre_action"}}]}}\n'
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"1",'
        '"content":"ack"}]}}'
    )
    fields = transcript_fields(parse_claude_stream_json(stream))
    assert fields.runtime_decisions[0]["stage"] == "pre_action"
    evaluated = evaluate_decisions(fields.runtime_decisions, threshold=0.5)
    assert evaluated["by_stage"]["pre_action"] == 1
    assert evaluated["stage_order_observed"] == ["pre_action"]
    assert "evidence" in DECISION_STAGE_INSTRUCTION


def test_staged_contract_reports_missing_stages_without_fabricating_them() -> None:
    result = evaluate_decisions(
        [{"decision": "abstain", "confidence": 0.2, "stage": "pre_action"}],
        required_stages=("pre_action", "evidence", "action", "final"),
    )
    assert result["stage_completeness"] == {
        "required": ["pre_action", "evidence", "action", "final"],
        "observed": ["pre_action"],
        "missing": ["evidence", "action", "final"],
        "complete": False,
        "order_valid": True,
    }


def test_terminal_echo_of_structured_output_is_not_counted_twice() -> None:
    payload = '{"decision":"abstain","confidence":0.2,"stage":"pre_action"}'
    stream = (
        '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"1",'
        '"name":"StructuredOutput","input":' + payload + '}]}}\n'
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"1",'
        '"content":"ack"}]}}\n'
        '{"type":"result","structured_output":' + payload + '}'
    )
    fields = transcript_fields(parse_claude_stream_json(stream))
    assert len(fields.runtime_decisions) == 1


def test_exact_json_result_is_recorded_but_prose_is_not() -> None:
    structured = (
        '{"decision":"abstain","confidence":0.22,"threshold":0.5,"reason":"missing evidence"}'
    )
    prose = "I could not complete it. " + structured
    assert transcript_fields(parse_claude_stream_json(json.dumps({
        "type": "result", "result": prose,
    }))).runtime_decisions == ()

    exact = json.dumps({"type": "result", "result": structured})
    fields = transcript_fields(parse_claude_stream_json(exact))
    assert fields.runtime_decisions[0]["decision"] == "abstain"
    assert fields.runtime_decisions[0]["source"] == "result.result"


def test_decision_prompt_defines_confidence_and_preserves_task() -> None:
    prompt = with_decision_output_instruction("make the change")
    assert prompt.startswith("make the change\n\n")
    assert "confidence" in prompt
    assert DECISION_OUTPUT_SCHEMA["required"] == ["decision", "confidence"]
