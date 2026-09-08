from harness.retrieval_trace import summarize_memory_calls


def test_memory_telemetry_separates_success_failure_abstention_hits_and_trust() -> None:
    result = summarize_memory_calls(
        [
            {
                "name": "mcp__recall__recall_search",
                "output": '{"evidence":[{"id":"a"}],"trust_state":"trusted"}',
                "is_error": False,
                "latency_ms": 12.0,
            },
            {
                "name": "mcp__recall__recall_search",
                "output": '{"abstained":true,"evidence":[],"trust_state":"abstained"}',
                "is_error": False,
            },
            {
                "name": "mcp__recall__recall_search",
                "output": "NoActiveGeneration",
                "is_error": True,
            },
            {"name": "Read", "output": "not memory", "is_error": False},
        ],
        memory_tool_prefix="mcp__recall__",
    )
    assert result["attempted"] == 3
    assert result["succeeded"] == 2
    assert result["failed"] == 1
    assert result["abstained"] == 1
    assert result["hits_returned"] == 1
    assert result["trust_states"] == ["trusted", "abstained"]
    assert result["error_codes"] == ["tool_error"]
    assert result["observations"][2]["status"] == "failed"


def test_claude_mem_progressive_search_count_is_recorded() -> None:
    result = summarize_memory_calls(
        [
            {
                "name": "mcp__mcp-search__search",
                "output": 'Found 35 result(s) matching "order ids"',
                "is_error": False,
            },
            {
                "name": "mcp__mcp-search__search",
                "output": 'Found 0 result(s) matching "absent"',
                "is_error": False,
            },
        ],
        memory_tool_prefix="mcp__mcp-search__",
    )
    assert result["hits_returned"] == 35
    assert [item["hits"] for item in result["observations"]] == [35, 0]
