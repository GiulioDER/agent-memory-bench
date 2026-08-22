"""Canonical JSON-compatible records for multi-arm agent benchmark runs.

Ported from recall's ``benchmarks/agent_ab/schema.py`` and generalised from a two-variant
(``recall_on`` / ``recall_off``) design to N named arms. Two properties carry over unchanged
because they were paid for:

- ``None`` means a value was not observed. It must never be replaced with zero, because an
  unmeasured value must remain distinguishable from a measured zero.
- A record is constructed complete or not at all: validation happens in ``__post_init__``,
  not in the analyser.

New in this repo: ``arm`` (an adapter name, not a role), ``seed`` (the repetition index of the
(task, seed) grid cell), ``config_dir_digest`` (sha256 of the generated ``CLAUDE_CONFIG_DIR``
tree, proving which integration the session ran with), and ``hook_ledger`` (the shim-recorded
lifecycle hook events, the admission signal for hook-based integrations).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

#: Memory tool calls are counted by prefix match over the session's tool calls. Each adapter
#: declares its own prefix; this default only names the metadata convention.
DEFAULT_MEMORY_TOOL_PREFIX = "mcp__"


def _check_optional_nonnegative(name: str, value: float | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a nonnegative number or None")
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(f"{name} must be finite or None")


def _tuple_of_strings(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a sequence of strings")
    return tuple(str(item) for item in value)


def _tuple_of_mappings(value: Any, name: str) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a sequence of mappings")
    result = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError(f"{name} items must be mappings")
        result.append(dict(item))
    return tuple(result)


@dataclass(frozen=True)
class SessionRecord:
    """One completed or failed task execution in one benchmark arm.

    ``arm`` is the adapter name (``bare``, ``claude_md``, ``fs_grep``, ``recall``, ``mem0``,
    ...), validated against the adapter registry by the runner, not here: the schema stays
    loadable for records written by an adapter this checkout does not know about.
    """

    task_id: str
    arm: str
    success: bool
    seed: int = 0
    user_input: str = ""
    response: str = ""
    reference: str | None = None
    retrieved_contexts: tuple[str, ...] = ()
    reference_contexts: tuple[str, ...] = ()
    conversation: tuple[dict[str, Any], ...] = ()
    reference_tool_calls: tuple[dict[str, Any], ...] = ()
    tool_calls: tuple[dict[str, Any], ...] = ()
    memory_call_count: int = 0
    memory_latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    model_turns: int | None = None
    wall_time_ms: float | None = None
    system_cost_usd: float | None = None
    evaluator_cost_usd: float | None = None
    abstained: bool = False
    trust_verdicts: tuple[str, ...] = ()
    config_dir_digest: str | None = None
    hook_ledger: tuple[dict[str, Any], ...] = ()
    error: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.arm.strip():
            raise ValueError("arm must not be empty")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a nonnegative int")
        if not isinstance(self.success, bool):
            raise TypeError("success must be a bool")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        if self.memory_call_count < 0:
            raise ValueError("memory_call_count must be nonnegative")
        for name in (
            "memory_latency_ms",
            "input_tokens",
            "output_tokens",
            "model_turns",
            "wall_time_ms",
            "system_cost_usd",
            "evaluator_cost_usd",
        ):
            _check_optional_nonnegative(name, getattr(self, name))
        # NOTE: the old schema refused memory calls on the off arm here. With N arms that rule
        # belongs to the gate (forbidden prefixes per arm), which can also DISCARD rather than
        # crash a loader that is trying to show you the contaminated record.

    @property
    def cell(self) -> tuple[str, int]:
        """The (task, seed) grid cell this record belongs to."""

        return (self.task_id, self.seed)

    @property
    def total_tokens(self) -> int | None:
        """Return measured model tokens, or None when either side is unavailable."""

        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens

    @property
    def is_complete(self) -> bool:
        """Whether the runner completed without an execution error."""

        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON serializable representation."""

        return {
            "record_version": 2,
            "task_id": self.task_id,
            "arm": self.arm,
            "seed": self.seed,
            "success": self.success,
            "user_input": self.user_input,
            "response": self.response,
            "reference": self.reference,
            "retrieved_contexts": list(self.retrieved_contexts),
            "reference_contexts": list(self.reference_contexts),
            "conversation": [dict(item) for item in self.conversation],
            "reference_tool_calls": [dict(item) for item in self.reference_tool_calls],
            "tool_calls": [dict(item) for item in self.tool_calls],
            "memory_call_count": self.memory_call_count,
            "memory_latency_ms": self.memory_latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "model_turns": self.model_turns,
            "wall_time_ms": self.wall_time_ms,
            "system_cost_usd": self.system_cost_usd,
            "evaluator_cost_usd": self.evaluator_cost_usd,
            "abstained": self.abstained,
            "trust_verdicts": list(self.trust_verdicts),
            "config_dir_digest": self.config_dir_digest,
            "hook_ledger": [dict(item) for item in self.hook_ledger],
            "error": self.error,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SessionRecord:
        """Construct a record from a runner result or a JSON object.

        Accepts version-1 records (the recall agent_ab format) by mapping ``variant`` to
        ``arm`` and the ``recall_*`` counters to the ``memory_*`` names, so the salvage and
        analysis tools can read old artifacts.
        """

        arm = value.get("arm", value.get("variant"))
        if arm is None:
            raise KeyError("record has neither 'arm' nor 'variant'")
        memory_calls = value.get("memory_call_count", value.get("recall_call_count", 0))
        memory_latency = value.get("memory_latency_ms", value.get("recall_latency_ms"))
        return cls(
            task_id=str(value["task_id"]),
            arm=str(arm),
            seed=int(value.get("seed", 0)),
            success=bool(value["success"]),
            user_input=str(value.get("user_input", "")),
            response=str(value.get("response", "")),
            reference=value.get("reference"),
            retrieved_contexts=_tuple_of_strings(
                value.get("retrieved_contexts"), "retrieved_contexts"
            ),
            reference_contexts=_tuple_of_strings(
                value.get("reference_contexts"), "reference_contexts"
            ),
            conversation=_tuple_of_mappings(value.get("conversation"), "conversation"),
            reference_tool_calls=_tuple_of_mappings(
                value.get("reference_tool_calls"), "reference_tool_calls"
            ),
            tool_calls=_tuple_of_mappings(value.get("tool_calls"), "tool_calls"),
            memory_call_count=int(memory_calls),
            memory_latency_ms=memory_latency,
            input_tokens=value.get("input_tokens"),
            output_tokens=value.get("output_tokens"),
            model_turns=value.get("model_turns"),
            wall_time_ms=value.get("wall_time_ms"),
            system_cost_usd=value.get("system_cost_usd"),
            evaluator_cost_usd=value.get("evaluator_cost_usd"),
            abstained=bool(value.get("abstained", False)),
            trust_verdicts=_tuple_of_strings(value.get("trust_verdicts"), "trust_verdicts"),
            config_dir_digest=value.get("config_dir_digest"),
            hook_ledger=_tuple_of_mappings(value.get("hook_ledger"), "hook_ledger"),
            error=value.get("error"),
            metadata=value.get("metadata", {}),
        )
