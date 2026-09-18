"""Build explicit sequence memory events from declared tool telemetry.

The benchmark must not infer an abstention from a missing tool call. An adapter declares which
fully qualified tools represent a memory write or retrieval, and this module emits an event only
when that tool was actually observed. Oracle labels are joined separately after execution and are
never accepted from tool output.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

EVENT_KINDS = ("write", "retrieve")
ORACLE_LABELS = ("useful", "harmful", "applied")


def _json_payload(output: Any) -> Mapping[str, Any] | None:
    if not isinstance(output, str):
        return None
    try:
        value = json.loads(output.strip())
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, Mapping) else None


def _payload_value(call: Mapping[str, Any], payload: Mapping[str, Any] | None, name: str) -> Any:
    value = call.get(name)
    if value is not None:
        return value
    return payload.get(name) if payload is not None else None


def _decision(kind: str, value: Any) -> str:
    allowed = ("write", "skip") if kind == "write" else ("retrieve", "abstain")
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in allowed:
            return candidate
        if kind == "retrieve" and candidate in {"escalate", "abstention"}:
            return "abstain"
    return allowed[0]


def validate_memory_event_tools(value: Mapping[str, str] | None) -> dict[str, str]:
    """Validate an adapter's exact tool to event-kind declaration."""

    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("memory_event_tools must be a mapping of tool names to event kinds")
    result: dict[str, str] = {}
    for tool, kind in value.items():
        tool_name = str(tool).strip()
        if not tool_name:
            raise ValueError("memory_event_tools tool names must not be empty")
        if kind not in EVENT_KINDS:
            raise ValueError(f"memory event kind must be one of {EVENT_KINDS}, got {kind!r}")
        result[tool_name] = kind
    return result


def memory_events_from_tool_calls(
    tool_calls: Sequence[Mapping[str, Any]],
    *,
    memory_event_tools: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Emit observed decisions for tools explicitly declared by an adapter.

    A tool invocation is evidence of the positive action for its declared kind. A producer may
    override that decision with a structured ``memory_decision`` on the call or in its JSON result.
    No event is emitted for an undeclared tool or for the absence of a call.
    """

    declared = validate_memory_event_tools(memory_event_tools)
    events: list[dict[str, Any]] = []
    for index, call in enumerate(tool_calls):
        tool = str(call.get("name", ""))
        kind = declared.get(tool)
        if kind is None:
            continue
        payload = _json_payload(call.get("output"))
        raw_decision = _payload_value(call, payload, "memory_decision")
        if raw_decision is None:
            raw_decision = _payload_value(call, payload, "decision")
        event: dict[str, Any] = {
            "kind": kind,
            "decision": _decision(kind, raw_decision),
            "source": f"tool_calls[{index}].{tool}",
        }
        events.append(event)
    return tuple(events)


def apply_oracle_labels(
    events: Sequence[Mapping[str, Any]],
    labels_by_source: Mapping[str, Mapping[str, bool | None]],
) -> tuple[dict[str, Any], ...]:
    """Attach preregistered labels to observed events by their stable source identifier.

    The label artifact is supplied by the trusted evaluator after a session finishes. Unknown
    event sources and non boolean labels are refused so a misspelled or self supplied label cannot
    silently change selectivity metrics.
    """

    if not isinstance(labels_by_source, Mapping):
        raise TypeError("oracle labels must be a mapping keyed by event source")
    event_sources = {str(event.get("source", "")) for event in events}
    unknown_sources = sorted(set(labels_by_source) - event_sources)
    if unknown_sources:
        raise ValueError(f"oracle labels reference unknown event sources: {unknown_sources}")
    labelled: list[dict[str, Any]] = []
    for event in events:
        source = str(event.get("source", ""))
        annotation = labels_by_source.get(source)
        result = dict(event)
        if annotation is not None:
            if not isinstance(annotation, Mapping):
                raise TypeError(f"oracle labels for {source!r} must be a mapping")
            for label, value in annotation.items():
                if label not in ORACLE_LABELS:
                    raise ValueError(f"unknown oracle memory label {label!r}")
                if value is not None and not isinstance(value, bool):
                    raise TypeError(f"oracle memory label {label!r} must be bool or None")
                result[label] = value
        labelled.append(result)
    return tuple(labelled)
