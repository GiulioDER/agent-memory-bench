"""Structured telemetry for memory tool calls.

The old record exposed only ``memory_call_count``.  That number cannot distinguish a healthy
empty result from a failed server, an explicit abstention, or a result carrying trusted evidence.
This module derives a deliberately small, JSON compatible summary from the captured tool calls.
It never treats prose as a hit or as a trust verdict.
"""

from __future__ import annotations

import json
import re
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
    pending = [payload]
    seen: set[int] = {id(payload)}
    while pending:
        current = pending.pop()
        for key in ("bundle", "result", "data", "diagnostics"):
            nested = current.get(key)
            if isinstance(nested, Mapping):
                decoded = [nested]
            elif isinstance(nested, str):
                decoded = _json_objects(nested)
            else:
                decoded = []
            for candidate in decoded:
                if id(candidate) in seen:
                    continue
                seen.add(id(candidate))
                candidates.append(candidate)
                pending.append(candidate)
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


_CLAUDE_MEM_RESULT_COUNT = re.compile(r"^\s*Found\s+(\d+)\s+result\(s\)\s+matching\b", re.MULTILINE)


def _progressive_result_count(output: str, tool_name: str) -> int | None:
    """Read Claude-Mem's progressive disclosure count without treating arbitrary prose as hits."""

    if not tool_name.startswith("mcp__mcp-search__"):
        return None
    match = _CLAUDE_MEM_RESULT_COUNT.search(output)
    return int(match.group(1)) if match else None


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
    graph_attempted = 0
    graph_succeeded = 0
    graph_relations_inspected = 0
    graph_modes: list[str] = []
    reranking_attempted = 0
    reranking_ran = 0
    rerank_ms: list[float] = []
    for index, call in enumerate(calls):
        output = call.get("output")
        is_error = bool(call.get("is_error"))
        payloads = _json_objects(output) if isinstance(output, str) else []
        payload = payloads[0] if payloads else None
        items = _items(payload) if payload is not None else None
        tool_name = str(call.get("name", ""))
        progressive_hits = (
            _progressive_result_count(output, tool_name) if isinstance(output, str) else None
        )
        hit_count = len(items) if items is not None else progressive_hits
        if hit_count is not None:
            hits_returned += hit_count
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
        is_graph = tool_name.endswith("recall_reasoning_query")
        if is_graph:
            graph_attempted += 1
            graph_succeeded += status == "succeeded"
            mode = _first(payload, ("graph_expansion_mode",)) if payload else None
            if isinstance(mode, str) and mode not in graph_modes:
                graph_modes.append(mode)
            relations = _first(payload, ("graph_relations_inspected",)) if payload else None
            if isinstance(relations, (int, float)) and not isinstance(relations, bool):
                graph_relations_inspected += int(relations)
        ran = _first(payload, ("reranking_ran",)) if payload else None
        if isinstance(ran, bool):
            reranking_attempted += 1
            reranking_ran += ran
        duration = _first(payload, ("rerank_ms",)) if payload else None
        if isinstance(duration, (int, float)) and not isinstance(duration, bool):
            rerank_ms.append(float(duration))
        observations.append(
            {
                "index": index,
                "tool": tool_name,
                "status": status,
                "abstained": abstained,
                "hits": hit_count,
                "trust_state": trust if isinstance(trust, str) else None,
                "error_code": error if isinstance(error, str) else None,
                "latency_ms": call.get("latency_ms"),
                "graph_expansion_mode": mode if is_graph and isinstance(mode, str) else None,
                "graph_relations_inspected": (
                    int(relations)
                    if is_graph and isinstance(relations, (int, float)) and not isinstance(relations, bool)
                    else None
                ),
                "reranking_ran": ran if isinstance(ran, bool) else None,
                "rerank_ms": float(duration)
                if isinstance(duration, (int, float)) and not isinstance(duration, bool)
                else None,
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
        "graph_calls_attempted": graph_attempted,
        "graph_calls_succeeded": graph_succeeded,
        "graph_relations_inspected": graph_relations_inspected,
        "graph_expansion_modes": graph_modes,
        "reranking_calls": reranking_attempted,
        "reranking_ran": reranking_ran,
        "rerank_ms": rerank_ms,
        "observations": observations,
    }
