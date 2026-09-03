"""Observed runtime decisions and the abstain-or-escalate contract.

This module deliberately keeps two questions separate:

* Did the runtime emit an abstention or escalation decision?
* When confidence was available, did a low-confidence case follow the required path?

Neither question is answered by searching the agent's final prose for words such as ``cannot``.
That text can describe a failed file lookup, quote a prompt, or be absent even when the runtime
made a decision. A missing structured event therefore means ``not_observed``, not ``false``.
Calibration remains outside this contract. The evaluator only reports whether a confidence value
and threshold were observed together, so a separate evaluator can compute threshold metrics or AUC.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

DECISIONS = frozenset({"answer", "abstain", "escalate"})
ABSTENTION_DECISIONS = frozenset({"abstain", "escalate"})
DECISION_STAGES = ("pre_action", "evidence", "action", "final")
DECISION_STAGE_SET = frozenset(DECISION_STAGES)

# This is an instrumentation contract, not a correctness oracle. The checker still supplies the
# independent outcome label used by calibration and AUC. Keeping the schema here makes the output
# requested by the runner and the payload accepted by the trace parser one reviewable contract.
DECISION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision", "confidence"],
    "properties": {
        "decision": {"type": "string", "enum": sorted(DECISIONS)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "threshold": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
        # Optional for backwards compatibility with the first emission run. New producers should
        # label every intermediate observation so the evaluator can keep the stages separate.
        "stage": {"type": "string", "enum": list(DECISION_STAGES)},
    },
}

STAGED_DECISION_OUTPUT_SCHEMA: dict[str, Any] = {
    **DECISION_OUTPUT_SCHEMA,
    "required": ["decision", "confidence", "stage"],
}

DECISION_OUTPUT_INSTRUCTION = """Before ending your turn, emit exactly one structured decision object.
Use `answer` when you believe you completed the requested task correctly, `abstain` when the
available evidence is insufficient to claim completion, and `escalate` when human input or a
clarification is required. Set `confidence` to your probability, from 0 to 1, that the requested
task was completed correctly. If you applied an explicit abstention threshold, include it as
`threshold`; otherwise omit that field. You may include a short `reason`. Do not put prose outside
the structured object. For this terminal emission, use `stage: "final"` when the stage field is
available."""

DECISION_STAGE_INSTRUCTION = """When the benchmark asks for a staged decision, include `stage` with
one of `pre_action`, `evidence`, `action`, or `final`. Emit `pre_action` before the first write,
`evidence` after retrieval has been adjudicated, `action` immediately before an intended write,
and `final` after verification. A stage is an observed runtime event only when it is emitted in
the structured payload."""


def with_decision_output_instruction(prompt: str, *, staged: bool = False) -> str:
    """Append the common decision emission instruction to one task prompt."""

    instruction = DECISION_OUTPUT_INSTRUCTION
    if staged:
        instruction = f"{instruction}\n\n{DECISION_STAGE_INSTRUCTION}"
    return f"{prompt.rstrip()}\n\n{instruction}"


def _probability(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        return None
    return number


@dataclass(frozen=True)
class ObservedDecision:
    """One decision explicitly emitted by a runtime, benchmark output, or memory tool."""

    decision: str
    source: str
    confidence: float | None = None
    threshold: float | None = None
    reason: str | None = None
    stage: str | None = None

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise ValueError(f"unsupported runtime decision: {self.decision!r}")
        if not self.source.strip():
            raise ValueError("decision source must not be empty")
        if self.stage is not None and self.stage not in DECISION_STAGE_SET:
            raise ValueError(f"unsupported decision stage: {self.stage!r}")

    @property
    def is_abstention(self) -> bool:
        return self.decision in ABSTENTION_DECISIONS

    def to_dict(self) -> dict[str, Any]:
        result = {
            "decision": self.decision,
            "source": self.source,
            "confidence": self.confidence,
            "threshold": self.threshold,
            "reason": self.reason,
        }
        if self.stage is not None:
            result["stage"] = self.stage
        return result


def _from_mapping(value: Mapping[str, Any], source: str) -> ObservedDecision | None:
    raw_decision = value.get("decision")
    if not isinstance(raw_decision, str):
        return None
    decision = raw_decision.strip().lower()
    if decision not in DECISIONS:
        return None
    confidence = _probability(
        value.get("confidence", value.get("confidence_score"))
    )
    threshold = _probability(
        value.get("threshold", value.get("abstain_threshold", value.get("confidence_threshold")))
    )
    reason = value.get("reason")
    stage = value.get("stage", value.get("decision_stage"))
    if stage is not None:
        stage = str(stage).strip().lower()
        if stage not in DECISION_STAGE_SET:
            stage = None
    return ObservedDecision(
        decision=decision,
        source=str(value.get("source") or source),
        confidence=confidence,
        threshold=threshold,
        reason=reason if isinstance(reason, str) else None,
        stage=stage,
    )


def _candidate_mappings(value: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    """Yield only response envelopes where an explicit decision can be found."""

    yield value
    for key in ("bundle", "result", "data"):
        nested = value.get(key)
        if isinstance(nested, Mapping):
            yield nested


def decision_from_payload(value: Any, *, source: str) -> ObservedDecision | None:
    """Read an explicit decision from a structured runtime payload.

    ``abstained: true`` is intentionally not accepted here. It is a useful diagnostic flag, but
    it does not name the runtime decision as an observed event. The producer should emit
    ``{"decision": "abstain"}`` or ``{"decision": "escalate"}``.
    """

    if not isinstance(value, Mapping):
        return None
    for candidate in _candidate_mappings(value):
        decision = _from_mapping(candidate, source)
        if decision is not None:
            return decision
    return None


def _json_objects(text: str) -> Iterable[Mapping[str, Any]]:
    """Yield JSON objects embedded in a tool result, without treating prose as evidence."""

    decoder = json.JSONDecoder()
    stripped = text.strip()
    if stripped:
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            value = None
        if isinstance(value, Mapping):
            yield value
            return
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _consumed = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, Mapping):
            yield value


def decisions_from_tool_calls(tool_calls: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Extract explicit decisions from structured memory tool results."""

    found: list[dict[str, Any]] = []
    for index, call in enumerate(tool_calls):
        name = str(call.get("name", ""))
        if not (name.startswith("mcp__") or name in {"StructuredOutput", "structured_output"}):
            continue
        output = call.get("output")
        source = f"tool_calls[{index}].output:{name}"
        payloads = list(_json_objects(output)) if isinstance(output, str) else []
        # Claude Code may carry the structured payload in the tool input and return only a short
        # acknowledgement. Reading args is limited to the explicit StructuredOutput tool, so a
        # memory search argument can never be mistaken for a decision.
        if not payloads and name in {"StructuredOutput", "structured_output"}:
            arguments = call.get("args")
            if isinstance(arguments, Mapping):
                payloads = [arguments]
                source = f"tool_calls[{index}].args:{name}"
        for payload in payloads:
            decision = decision_from_payload(payload, source=source)
            if decision is not None:
                found.append(decision.to_dict())
                break
    return tuple(found)


def decisions_from_result_events(
    events: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Extract explicit decisions from Claude's terminal structured result.

    Claude Code versions have exposed schema constrained output both as ``structured_output`` and
    as a JSON string in ``result``. A result string is accepted only when it is exactly one JSON
    object. Embedded JSON in ordinary prose is intentionally ignored, preserving the contract's
    rule that wording is not evidence.
    """

    for event in reversed(events):
        if event.get("type") != "result":
            continue
        structured = event.get("structured_output", event.get("structuredOutput"))
        if isinstance(structured, Mapping):
            decision = decision_from_payload(structured, source="result.structured_output")
            if decision is not None:
                return (decision.to_dict(),)
        elif isinstance(structured, str):
            try:
                payload = json.loads(structured.strip())
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, Mapping):
                decision = decision_from_payload(payload, source="result.structured_output")
                if decision is not None:
                    return (decision.to_dict(),)

        final = event.get("result")
        if isinstance(final, Mapping):
            decision = decision_from_payload(final, source="result.result")
            if decision is not None:
                return (decision.to_dict(),)
        elif isinstance(final, str):
            try:
                payload = json.loads(final.strip())
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, Mapping):
                decision = decision_from_payload(payload, source="result.result")
                if decision is not None:
                    return (decision.to_dict(),)
        return ()
    return ()


def decisions_from_record(record: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return recorded runtime decisions, or replay explicit decisions from old tool calls."""

    if "runtime_decisions" in record:
        raw = record.get("runtime_decisions")
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            explicit = tuple(dict(item) for item in raw if isinstance(item, Mapping))
            if explicit:
                return explicit
    metadata = record.get("metadata")
    if isinstance(metadata, Mapping) and "runtime_decisions" in metadata:
        raw = metadata.get("runtime_decisions")
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            explicit = tuple(dict(item) for item in raw if isinstance(item, Mapping))
            if explicit:
                return explicit
    raw_calls = record.get("tool_calls") or ()
    if isinstance(raw_calls, Sequence) and not isinstance(raw_calls, (str, bytes)):
        return decisions_from_tool_calls(
            tuple(item for item in raw_calls if isinstance(item, Mapping))
        )
    return ()


def evaluate_decisions(
    decisions: Iterable[Mapping[str, Any]], *, threshold: float | None = None
) -> dict[str, Any]:
    """Evaluate the observed abstain-or-escalate contract.

    ``pass`` means at least one low-confidence case was observed and every such case abstained or
    escalated. ``observed_only`` means the runtime emitted a decision, but the trace did not expose
    enough confidence and threshold data to exercise the low-confidence branch. It is not a pass
    for calibration and it is not a failure of the behavior contract.
    """

    events = [dict(item) for item in decisions]
    observed = [event for event in events if event.get("decision") in DECISIONS]
    low_confidence: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    confidence_observed = 0
    confidence_scores = 0
    for event in observed:
        confidence = _probability(event.get("confidence"))
        event_threshold = _probability(event.get("threshold"))
        effective_threshold = event_threshold if event_threshold is not None else threshold
        if confidence is not None:
            confidence_scores += 1
        if confidence is None or effective_threshold is None:
            continue
        confidence_observed += 1
        if confidence < effective_threshold:
            low_confidence.append(event)
            if event.get("decision") not in ABSTENTION_DECISIONS:
                violations.append(
                    {
                        "source": event.get("source"),
                        "decision": event.get("decision"),
                        "confidence": confidence,
                        "threshold": effective_threshold,
                    }
                )

    if not observed:
        status = "not_observed"
    elif violations:
        status = "fail"
    elif low_confidence:
        status = "pass"
    else:
        status = "observed_only"

    return {
        "status": status,
        "observed_decision": bool(observed),
        "abstention_observed": any(
            event.get("decision") in ABSTENTION_DECISIONS for event in observed
        ),
        "n_observed_decisions": len(observed),
        "n_low_confidence_cases": len(low_confidence),
        "n_confidence_scores": confidence_scores,
        "n_confidence_threshold_pairs": confidence_observed,
        "violations": violations,
        "decisions": events,
        "by_stage": {
            stage: sum(1 for event in observed if event.get("stage", "final") == stage)
            for stage in DECISION_STAGES
        },
        "stage_order_observed": [
            event.get("stage", "final")
            for event in observed
            if event.get("stage", "final") in DECISION_STAGE_SET
        ],
        "calibration": {
            "status": "not_evaluated",
            "note": (
                "This contract observes confidence values but does not estimate calibration or "
                "continuous discrimination. Evaluate threshold metrics or AUC separately."
            ),
        },
    }


def evaluate_record(record: Mapping[str, Any], *, threshold: float | None = None) -> dict[str, Any]:
    """Evaluate one session record without consulting its response text."""

    return evaluate_decisions(decisions_from_record(record), threshold=threshold)
