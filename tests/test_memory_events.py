"""Tests for explicit sequence memory event production."""

from __future__ import annotations

import pytest

from harness.memory_events import apply_oracle_labels, memory_events_from_tool_calls


def test_declared_calls_produce_observed_events_without_self_supplied_labels():
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
        },
    )


def test_oracle_labels_are_joined_only_by_trusted_source():
    events = memory_events_from_tool_calls(
        [{"name": "mcp__memory__search", "output": '{"decision":"retrieve"}'}],
        memory_event_tools={"mcp__memory__search": "retrieve"},
    )
    assert apply_oracle_labels(
        events,
        {
            "tool_calls[0].mcp__memory__search": {
                "useful": True,
                "harmful": False,
                "applied": True,
            }
        },
    )[0]["useful"] is True


def test_oracle_labels_refuse_unknown_sources_and_non_boolean_values():
    events = memory_events_from_tool_calls(
        [{"name": "mcp__memory__search"}],
        memory_event_tools={"mcp__memory__search": "retrieve"},
    )
    with pytest.raises(ValueError, match="unknown event sources"):
        apply_oracle_labels(events, {"wrong-source": {"useful": True}})
    with pytest.raises(TypeError, match="must be bool"):
        apply_oracle_labels(
            events,
            {"tool_calls[0].mcp__memory__search": {"useful": "yes"}},
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
