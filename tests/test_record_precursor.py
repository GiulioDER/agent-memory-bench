from datetime import UTC, datetime

from scripts.record_precursor import conversation_to_corpus


def test_tool_results_are_paired_by_id_when_results_arrive_out_of_order():
    conversation = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call-a", "name": "Read", "args": {"path": "a"}},
                {"id": "call-b", "name": "Read", "args": {"path": "b"}},
            ],
        },
        {"role": "tool", "tool_use_id": "call-b", "content": "result-b"},
        {"role": "tool", "tool_use_id": "call-a", "content": "result-a"},
    ]

    lines = conversation_to_corpus("inspect", conversation, "done", datetime(2026, 1, 1, tzinfo=UTC))

    assert [line["tool_input"] for line in lines[1:3]] == [
        '{"path": "b"}',
        '{"path": "a"}',
    ]
    assert [line["tool_result"] for line in lines[1:3]] == ["result-b", "result-a"]
