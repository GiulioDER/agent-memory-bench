"""Structured telemetry for memory tool calls.

The old record exposed only ``memory_call_count``.  That number cannot distinguish a healthy
empty result from a failed server, an explicit abstention, or a result carrying trusted evidence.
This module derives a deliberately small, JSON compatible summary from the captured tool calls.
It never treats prose as a hit or as a trust verdict.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


def _json_objects(text: str) -> list[Mapping[str, Any]]:
    try:
        value = json.loads(text.strip())
    except (TypeError, json.JSONDecodeError):
        return []
    if isinstance(value, Mapping):
        return [value]
    return []


def _payload_candidates(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidates = [payload]
    for key in ("bundle", "result", "data"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            candidates.append(nested)
    return candidates


def _items(payload: Mapping[str, Any]) -> list[Any] | None:
    for candidate in _payload_candidates(payload):
        for key in ("items", "hits", "results", "evidence"):
            value = candidate.get(key)
            if isinstance(value, list):
                return value
    return None


def _first(payload: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for candidate in _payload_candidates(payload):
        for key in keys:
            if key in candidate:
                return candidate[key]
    return None


def summarize_memory_calls(
    tool_calls: Sequence[Mapping[str, Any]], *, memory_tool_prefix: str
) -> dict[str, Any]:
    """Summarize attempted memory calls without collapsing distinct failure modes."""

    calls = [
        call for call in tool_calls
        if str(call.get("name", "")).startswith(memory_tool_prefix)
    ]
    observations: list[dict[str, Any]] = []
    trust_states: list[str] = []
    error_codes: list[str] = []
    hits_returned = 0
    for index, call in enumerate(calls):
        output = call.get("output")
        is_error = bool(call.get("is_error"))
        payloads = _json_objects(output) if isinstance(output, str) else []
        payload = payloads[0] if payloads else None
        items = _items(payload) if payload is not None else None
        if items is not None:
            hits_returned += len(items)
        trust = _first(payload, ("trust_state", "trust_verdict", "gating", "trust")) if payload else None
        if isinstance(trust, str) and trust not in trust_states:
            trust_states.append(trust)
        error = _first(payload, ("error_code", "failure_code", "code", "type")) if payload else None
        if is_error and not isinstance(error, str):
            error = "tool_error"
        if isinstance(error, str) and error not in error_codes:
            error_codes.append(error)
        decision = _first(payload, ("decision",)) if payload else None
        abstained = bool(payload and _first(payload, ("abstained",)) is True) or (
            isinstance(decision, str) and decision in {"abstain", "escalate"}
        )
        if is_error:
            status = "failed"
        elif output is None:
            status = "unresolved"
        else:
            status = "succeeded"
        observations.append(
            {
                "index": index,
                "tool": str(call.get("name", "")),
                "status": status,
                "abstained": abstained,
                "hits": len(items) if items is not None else None,
                "trust_state": trust if isinstance(trust, str) else None,
                "error_code": error if isinstance(error, str) else None,
                "latency_ms": call.get("latency_ms"),
            }
        )
    return {
        "attempted": len(calls),
        "succeeded": sum(item["status"] == "succeeded" for item in observations),
        "failed": sum(item["status"] == "failed" for item in observations),
        "unresolved": sum(item["status"] == "unresolved" for item in observations),
        "abstained": sum(item["abstained"] for item in observations),
        "hits_returned": hits_returned,
        "trust_states": trust_states,
        "error_codes": error_codes,
        "observations": observations,
    }
