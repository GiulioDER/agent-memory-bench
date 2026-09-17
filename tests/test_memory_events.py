"""Tests for explicit sequence memory event production."""

from __future__ import annotations

import pytest

from harness.memory_events import memory_events_from_tool_calls


def test_declared_calls_produce_events_and_preserve_structured_labels():
    events = memory_events_from_tool_calls(
        [
            {
                "name": "mcp__memory__search",
                "output": '{"decision":"abstain","useful":true}',
            },
            {
                "name": "mcp__other__search",
                "output": '{"decision":"retrieve"}',
            },
        ],
        memory_event_tools={"mcp__memory__search": "retrieve"},
    )
    assert events == (
        {
            "kind": "retrieve",
            "decision": "abstain",
            "source": "tool_calls[0].mcp__memory__search",
            "useful": True,
        },
    )


def test_missing_calls_do_not_become_abstentions():
    assert memory_events_from_tool_calls(
        [], memory_event_tools={"mcp__memory__search": "retrieve"}
    ) == ()


def test_invalid_event_kind_is_refused():
    with pytest.raises(ValueError, match="memory event kind"):
        memory_events_from_tool_calls(
            [], memory_event_tools={"mcp__memory__search": "unknown"}
        )
