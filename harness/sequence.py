"""Sequence level scoring for longitudinal memory evaluations.

The ordinary benchmark scores one task and one session at a time. This module adds a stricter
boundary for linked work: a chain is admitted only when every expected session is present and
marked admitted. Missing metadata, duplicate attempts, and unobserved labels are refusals or
``None`` values, never silently converted into failures.

The runner records the sequence contract in ``SessionRecord.metadata``::

    {
        "sequence": {
            "chain_id": "chain-01",
            "length": 4,
            "position": 3,
            "role": "target",
            "admitted": true
        },
        "memory_events": [
            {"kind": "write", "decision": "write", "useful": true},
            {"kind": "retrieve", "decision": "abstain", "useful": false}
        ],
        "memory_input_tokens": 1200,
        "memory_output_tokens": 80
    }

``useful`` and ``harmful`` are labels supplied by the preregistered task oracle. Their absence
means unknown. A system is not rewarded for abstaining from a write that was never labelled, and
an unlabelled event cannot lower precision.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .schema import SessionRecord

SEQUENCE_KEY = "sequence"
MEMORY_EVENTS_KEY = "memory_events"
TARGET_ROLE = "target"
EVENT_KINDS = ("write", "retrieve")
FUNNEL_LABELS = ("encountered", "retained", "retrieved", "applied")


def _mapping(record: SessionRecord | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(record, SessionRecord):
        return record.metadata
    metadata = record.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise TypeError("record metadata must be a mapping")
    return metadata


def _record_value(record: SessionRecord | Mapping[str, Any], name: str) -> Any:
    if isinstance(record, SessionRecord):
        return getattr(record, name)
    return record.get(name)


def _sequence(record: SessionRecord | Mapping[str, Any]) -> dict[str, Any]:
    value = _mapping(record).get(SEQUENCE_KEY)
    if not isinstance(value, Mapping):
        raise ValueError(  # noqa: TRY004
            "sequence scoring requires metadata.sequence with chain_id, length, position, "
            "role, and admitted"
        )
    required = ("chain_id", "length", "position", "role", "admitted")
    missing = [name for name in required if name not in value]
    if missing:
        raise ValueError(f"sequence metadata is missing {', '.join(missing)}")
    chain_id = str(value["chain_id"]).strip()
    if not chain_id:
        raise ValueError("sequence.chain_id must not be empty")
    length = value["length"]
    position = value["position"]
    if isinstance(length, bool) or not isinstance(length, int) or length < 2:
        raise ValueError("sequence.length must be an int of at least 2")
    if isinstance(position, bool) or not isinstance(position, int) or not 0 <= position < length:
        raise ValueError("sequence.position must be an int within sequence.length")
    if not isinstance(value["admitted"], bool):
        raise TypeError("sequence.admitted must be a bool")
    return {
        "chain_id": chain_id,
        "length": length,
        "position": position,
        "role": str(value["role"]),
        "admitted": value["admitted"],
    }


def _events(record: SessionRecord | Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    value = _mapping(record).get(MEMORY_EVENTS_KEY, ())
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("metadata.memory_events must be a sequence of mappings")
    result: list[Mapping[str, Any]] = []
    for event in value:
        if not isinstance(event, Mapping):
            raise TypeError("metadata.memory_events items must be mappings")
        kind = event.get("kind")
        if kind not in EVENT_KINDS:
            raise ValueError(f"memory event kind must be one of {EVENT_KINDS}, got {kind!r}")
        decision = event.get("decision")
        valid_decisions = ("write", "skip") if kind == "write" else ("retrieve", "abstain")
        if decision not in valid_decisions:
            raise ValueError(
                f"{kind} event decision must be one of {valid_decisions}, got {decision!r}"
            )
        for label in ("useful", "harmful", "applied"):
            if label in event and event[label] is not None and not isinstance(event[label], bool):
                raise TypeError(f"memory event {label} must be bool or None")
        result.append(event)
    return tuple(result)


def _funnel(record: SessionRecord | Mapping[str, Any]) -> Mapping[str, bool | None]:
    value = _mapping(record).get("sequence_funnel", {})
    if isinstance(value, (str, bytes)) or not isinstance(value, Mapping):
        raise TypeError("metadata.sequence_funnel must be a mapping")
    unknown = sorted(set(value) - set(FUNNEL_LABELS))
    if unknown:
        raise ValueError(f"unknown sequence funnel labels: {unknown}")
    for label, item in value.items():
        if item is not None and not isinstance(item, bool):
            raise TypeError(f"sequence funnel label {label!r} must be bool or None")
    return value


def _observed_rate(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def _optional_sum(values: list[Any]) -> int | None:
    if not values or any(value is None for value in values):
        return None
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise ValueError("token and storage overhead values must be nonnegative integers")
    return sum(values)


@dataclass(frozen=True)
class _Chain:
    chain_id: str
    length: int
    records: dict[str, dict[int, SessionRecord | Mapping[str, Any]]]

    @property
    def arms(self) -> tuple[str, ...]:
        return tuple(sorted(self.records))

    def for_arm(self, arm: str) -> tuple[SessionRecord | Mapping[str, Any], ...]:
        return tuple(self.records[arm][position] for position in sorted(self.records[arm]))

    def is_admitted(self, arm: str) -> bool:
        by_position = self.records.get(arm, {})
        if set(by_position) != set(range(self.length)):
            return False
        return all(
            _sequence(record)["admitted"] and _record_value(record, "error") is None
            for record in by_position.values()
        )

    def target(self, arm: str) -> SessionRecord | Mapping[str, Any]:
        targets = [record for record in self.for_arm(arm) if _sequence(record)["role"] == TARGET_ROLE]
        if len(targets) != 1:
            raise ValueError(
                f"chain {self.chain_id!r}, arm {arm!r} must have exactly one target record"
            )
        return targets[0]


def _load_chains(records: Sequence[SessionRecord | Mapping[str, Any]]) -> tuple[_Chain, ...]:
    grouped: dict[str, dict[str, dict[int, SessionRecord | Mapping[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    lengths: dict[str, int] = {}
    for record in records:
        sequence = _sequence(record)
        chain_id = sequence["chain_id"]
        arm = str(_record_value(record, "arm"))
        position = sequence["position"]
        if chain_id in lengths and lengths[chain_id] != sequence["length"]:
            raise ValueError(f"chain {chain_id!r} has inconsistent sequence lengths")
        lengths[chain_id] = sequence["length"]
        if position in grouped[chain_id][arm]:
            raise ValueError(
                f"chain {chain_id!r}, arm {arm!r}, position {position} appears more than once; "
                "pass one final record per session"
            )
        grouped[chain_id][arm][position] = record
    return tuple(
        _Chain(chain_id=chain_id, length=lengths[chain_id], records=records_by_arm)
        for chain_id, records_by_arm in sorted(grouped.items())
    )


def _empty_event_metrics() -> dict[str, Any]:
    return {
        "write_decisions": 0,
        "writes": 0,
        "write_skips": 0,
        "write_useful_observed": 0,
        "write_useful": 0,
        "write_precision": None,
        "write_abstention_rate": None,
        "write_useful_abstentions": 0,
        "write_useful_abstention_rate": None,
        "retrieval_decisions": 0,
        "retrievals": 0,
        "retrieval_abstentions": 0,
        "retrieval_useful_observed": 0,
        "retrieval_useful": 0,
        "retrieval_precision": None,
        "retrieval_abstention_rate": None,
        "retrieval_harm_observed": 0,
        "retrieval_harmful": 0,
        "retrieval_harm_rate": None,
        "retrieval_useful_abstentions": 0,
        "retrieval_useful_abstention_rate": None,
        "useful_abstentions": 0,
    }


def _empty_funnel_metrics() -> dict[str, Any]:
    return {
        label: {"observed": 0, "successes": 0, "rate": None}
        for label in FUNNEL_LABELS
    }


def _add_funnel(metrics: dict[str, Any], records: Sequence[SessionRecord | Mapping[str, Any]]) -> None:
    source = next(record for record in records if _sequence(record)["role"] == "source")
    target = next(record for record in records if _sequence(record)["role"] == TARGET_ROLE)
    values = {**_funnel(source), **_funnel(target)}
    previous: bool | None = None
    for index, label in enumerate(FUNNEL_LABELS):
        value = values.get(label)
        if index == 0:
            if value is None:
                previous = None
                continue
            row = metrics[label]
            row["observed"] += 1
            row["successes"] += int(value)
            row["rate"] = row["successes"] / row["observed"]
            previous = value
            continue
        if previous is not True or value is None:
            previous = value
            continue
        row = metrics[label]
        row["observed"] += 1
        row["successes"] += int(value)
        row["rate"] = row["successes"] / row["observed"]
        previous = value


def _add_events(metrics: dict[str, Any], records: Sequence[SessionRecord | Mapping[str, Any]]) -> None:
    for record in records:
        for event in _events(record):
            kind = event["kind"]
            decision = event["decision"]
            useful = event.get("useful")
            harmful = event.get("harmful")
            if kind == "write":
                metrics["write_decisions"] += 1
                if decision == "write":
                    metrics["writes"] += 1
                    if useful is not None:
                        metrics["write_useful_observed"] += 1
                        metrics["write_useful"] += useful
                else:
                    metrics["write_skips"] += 1
                    if useful is True:
                        metrics["write_useful_abstentions"] += 1
            else:
                metrics["retrieval_decisions"] += 1
                if decision == "retrieve":
                    metrics["retrievals"] += 1
                    if useful is not None:
                        metrics["retrieval_useful_observed"] += 1
                        metrics["retrieval_useful"] += useful
                    if harmful is not None:
                        metrics["retrieval_harm_observed"] += 1
                        metrics["retrieval_harmful"] += harmful
                else:
                    metrics["retrieval_abstentions"] += 1
                    if useful is True:
                        metrics["retrieval_useful_abstentions"] += 1
    metrics["write_precision"] = _observed_rate(
        [True] * metrics["write_useful"]
        + [False] * (metrics["write_useful_observed"] - metrics["write_useful"])
    )
    metrics["write_abstention_rate"] = (
        metrics["write_skips"] / metrics["write_decisions"]
        if metrics["write_decisions"]
        else None
    )
    metrics["write_useful_abstention_rate"] = (
        metrics["write_useful_abstentions"] / metrics["write_skips"]
        if metrics["write_skips"]
        else None
    )
    metrics["retrieval_precision"] = _observed_rate(
        [True] * metrics["retrieval_useful"]
        + [False] * (metrics["retrieval_useful_observed"] - metrics["retrieval_useful"])
    )
    metrics["retrieval_abstention_rate"] = (
        metrics["retrieval_abstentions"] / metrics["retrieval_decisions"]
        if metrics["retrieval_decisions"]
        else None
    )
    metrics["retrieval_useful_abstention_rate"] = (
        metrics["retrieval_useful_abstentions"] / metrics["retrieval_abstentions"]
        if metrics["retrieval_abstentions"]
        else None
    )
    metrics["useful_abstentions"] = (
        metrics["write_useful_abstentions"] + metrics["retrieval_useful_abstentions"]
    )
    metrics["retrieval_harm_rate"] = _observed_rate(
        [True] * metrics["retrieval_harmful"]
        + [False] * (metrics["retrieval_harm_observed"] - metrics["retrieval_harmful"])
    )


def _chain_overhead(records: Sequence[SessionRecord | Mapping[str, Any]]) -> dict[str, int | None]:
    metadata = [_mapping(record) for record in records]
    return {
        "input_tokens": _optional_sum([_record_value(record, "input_tokens") for record in records]),
        "output_tokens": _optional_sum([_record_value(record, "output_tokens") for record in records]),
        "total_tokens": _optional_sum(
            [
                (
                    _record_value(record, "input_tokens") + _record_value(record, "output_tokens")
                    if _record_value(record, "input_tokens") is not None
                    and _record_value(record, "output_tokens") is not None
                    else None
                )
                for record in records
            ]
        ),
        "memory_input_tokens": _optional_sum(
            [metadata_item.get("memory_input_tokens") for metadata_item in metadata]
        ),
        "memory_output_tokens": _optional_sum(
            [metadata_item.get("memory_output_tokens") for metadata_item in metadata]
        ),
        "memory_storage_bytes": _optional_sum(
            [metadata_item.get("memory_storage_bytes") for metadata_item in metadata]
        ),
    }


def score_sequences(
    records: Sequence[SessionRecord | Mapping[str, Any]], *, baseline_arm: str = "bare"
) -> dict[str, Any]:
    """Score admitted longitudinal chains and memory selectivity.

    The primary chain outcome is target success among admitted chains, grouped by chain length.
    ``all_sessions_success_rate`` is reported beside it because a product can reach the target
    after failing an intermediate task. Paired harm is descriptive: it counts a memory arm's
    failed target against a matched baseline target that passed, but does not claim a causal
    counterfactual.
    """

    if not records:
        raise ValueError("sequence scoring requires at least one record")
    chains = _load_chains(records)
    arms = sorted({arm for chain in chains for arm in chain.arms})
    if baseline_arm not in arms:
        raise ValueError(f"baseline arm {baseline_arm!r} is absent from sequence records")

    by_arm_length: dict[tuple[str, int], dict[str, Any]] = {}
    for arm in arms:
        for length in sorted({chain.length for chain in chains}):
            by_arm_length[(arm, length)] = {
                "arm": arm,
                "length": length,
                "chains_total": 0,
                "admitted_chains": 0,
                "target_successes": 0,
                "target_success_rate": None,
                "all_sessions_successes": 0,
                "all_sessions_success_rate": None,
                "paired_harm_n": 0,
                "paired_harm_denominator": 0,
                "paired_harm_rate": None,
                "overhead": {
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                    "memory_input_tokens": None,
                    "memory_output_tokens": None,
                    "memory_storage_bytes": None,
                    "chains_metered": 0,
                    "mean_total_token_delta_vs_baseline": None,
                    "token_delta_pairs": 0,
                },
                "selectivity": _empty_event_metrics(),
                "funnel": _empty_funnel_metrics(),
            }

    for chain in chains:
        baseline_admitted = chain.is_admitted(baseline_arm)
        baseline_success = None
        if baseline_admitted:
            baseline_success = bool(_record_value(chain.target(baseline_arm), "success"))
        for arm in chain.arms:
            row = by_arm_length[(arm, chain.length)]
            row["chains_total"] += 1
            if not chain.is_admitted(arm):
                continue
            row["admitted_chains"] += 1
            arm_records = chain.for_arm(arm)
            target_success = bool(_record_value(chain.target(arm), "success"))
            row["target_successes"] += target_success
            row["all_sessions_successes"] += all(
                bool(_record_value(record, "success")) for record in arm_records
            )
            _add_events(row["selectivity"], arm_records)
            _add_funnel(row["funnel"], arm_records)
            overhead = _chain_overhead(arm_records)
            overhead_row = row["overhead"]
            metered_fields = (
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "memory_input_tokens",
                "memory_output_tokens",
                "memory_storage_bytes",
            )
            for field in metered_fields:
                if overhead[field] is not None:
                    previous = overhead_row[field]
                    overhead_row[field] = (previous or 0) + overhead[field]
            if overhead["total_tokens"] is not None:
                overhead_row["chains_metered"] += 1
            if arm != baseline_arm and baseline_success is not None:
                row["paired_harm_denominator"] += baseline_success
                row["paired_harm_n"] += baseline_success and not target_success
                if baseline_admitted:
                    baseline_total = _chain_overhead(chain.for_arm(baseline_arm))["total_tokens"]
                    if baseline_total is not None and overhead["total_tokens"] is not None:
                        current_pairs = overhead_row["token_delta_pairs"]
                        current_delta = overhead_row["mean_total_token_delta_vs_baseline"] or 0
                        overhead_row["mean_total_token_delta_vs_baseline"] = (
                            current_delta * current_pairs + overhead["total_tokens"] - baseline_total
                        ) / (current_pairs + 1)
                        overhead_row["token_delta_pairs"] += 1

    for row in by_arm_length.values():
        admitted = row["admitted_chains"]
        row["target_success_rate"] = row["target_successes"] / admitted if admitted else None
        row["all_sessions_success_rate"] = (
            row["all_sessions_successes"] / admitted if admitted else None
        )
        row["paired_harm_rate"] = (
            row["paired_harm_n"] / row["paired_harm_denominator"]
            if row["paired_harm_denominator"]
            else None
        )

    return {
        "schema": 1,
        "baseline_arm": baseline_arm,
        "arms": arms,
        "chains": len(chains),
        "metrics": [by_arm_length[key] for key in sorted(by_arm_length)],
        "interpretation": (
            "Paired harm is a descriptive baseline contrast, not a causal counterfactual. "
            "Precision and harm rates use only events carrying an oracle label; missing labels "
            "remain unobserved."
        ),
    }
