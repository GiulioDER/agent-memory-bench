"""Validated, post run oracle labels for sequence memory events.

Labels are kept outside runner records until evaluation. The artifact binds them to the sequence
plan and held out manifest, then joins them to observed events by chain, arm, position, and event
source. A label cannot create an event that was not observed by the runner.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .memory_events import ORACLE_LABELS, apply_oracle_labels
from .schema import SessionRecord

LABEL_SCHEMA = 1


def _digest(value: Any, name: str) -> str:
    digest = str(value).strip()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"{name} must be a lowercase SHA256 digest")
    return digest


def _session_key(sequence: Mapping[str, Any], arm: str) -> tuple[str, str, int]:
    chain_id = str(sequence.get("chain_id", "")).strip()
    position = sequence.get("position")
    if not chain_id or isinstance(position, bool) or not isinstance(position, int) or position < 0:
        raise ValueError("oracle label session needs chain_id and a nonnegative position")
    return chain_id, arm, position


@dataclass(frozen=True)
class OracleLabelSet:
    label_set_id: str
    sequence_plan_id: str
    evaluation_manifest_id: str
    evaluation_manifest_digest: str
    labels: dict[tuple[str, str, int], dict[str, dict[str, bool | None]]]
    data: dict[str, Any]


def load_label_set(data: Mapping[str, Any]) -> OracleLabelSet:
    """Validate a post run label artifact before it can affect scoring."""

    if data.get("schema") != LABEL_SCHEMA:
        raise ValueError(f"unsupported sequence label schema {data.get('schema')!r}")
    label_set_id = str(data.get("label_set_id", "")).strip()
    plan_id = str(data.get("sequence_plan_id", "")).strip()
    manifest_id = str(data.get("evaluation_manifest_id", "")).strip()
    if not label_set_id or not plan_id or not manifest_id:
        raise ValueError("oracle label set needs label_set_id, sequence_plan_id, and manifest id")
    manifest_digest = _digest(
        data.get("evaluation_manifest_digest"), "evaluation_manifest_digest"
    )
    sessions = data.get("sessions")
    if isinstance(sessions, (str, bytes)) or not isinstance(sessions, list):
        raise ValueError(  # noqa: TRY004 - malformed label artifacts use one stable validation error
            "oracle label set sessions must be a list"
        )
    labels: dict[tuple[str, str, int], dict[str, dict[str, bool | None]]] = {}
    for session_index, raw_session in enumerate(sessions):
        if not isinstance(raw_session, Mapping):
            raise TypeError(f"oracle label session {session_index} must be an object")
        sequence = raw_session.get("sequence")
        if not isinstance(sequence, Mapping):
            raise TypeError(f"oracle label session {session_index}.sequence must be an object")
        arm = str(raw_session.get("arm", "")).strip()
        if not arm:
            raise ValueError(f"oracle label session {session_index} needs an arm")
        key = _session_key(sequence, arm)
        if key in labels:
            raise ValueError(f"oracle label session {key!r} appears more than once")
        events = raw_session.get("events", [])
        if isinstance(events, (str, bytes)) or not isinstance(events, list):
            raise ValueError(  # noqa: TRY004 - malformed label artifacts use one stable error
                f"oracle label session {key!r}.events must be a list"
            )
        by_source: dict[str, dict[str, bool | None]] = {}
        for event_index, raw_event in enumerate(events):
            if not isinstance(raw_event, Mapping):
                raise TypeError(f"oracle label event {key!r}/{event_index} must be an object")
            source = str(raw_event.get("source", "")).strip()
            if not source:
                raise ValueError(f"oracle label event {key!r}/{event_index} needs a source")
            if source in by_source:
                raise ValueError(f"oracle label source {source!r} appears more than once")
            annotation: dict[str, bool | None] = {}
            for label, value in raw_event.items():
                if label == "source":
                    continue
                if label not in ORACLE_LABELS:
                    raise ValueError(f"unknown oracle memory label {label!r}")
                if value is not None and not isinstance(value, bool):
                    raise TypeError(f"oracle memory label {label!r} must be bool or None")
                annotation[label] = value
            if not annotation:
                raise ValueError(f"oracle label event {key!r}/{event_index} has no labels")
            by_source[source] = annotation
        labels[key] = by_source
    return OracleLabelSet(
        label_set_id,
        plan_id,
        manifest_id,
        manifest_digest,
        labels,
        dict(data),
    )


def load_label_set_file(path: str | Path) -> OracleLabelSet:
    label_path = Path(path)
    data = json.loads(label_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise TypeError("oracle label set root must be an object")
    return load_label_set(data)


def _record_metadata(record: SessionRecord | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(record, SessionRecord):
        return record.metadata
    metadata = record.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise TypeError("record metadata must be a mapping")
    return metadata


def apply_label_set(
    records: Sequence[SessionRecord | Mapping[str, Any]], label_set: OracleLabelSet
) -> tuple[SessionRecord | Mapping[str, Any], ...]:
    """Apply labels to matching observed records and refuse labels for absent events."""

    output: list[SessionRecord | Mapping[str, Any]] = []
    matched_sessions: set[tuple[str, str, int]] = set()
    for record in records:
        metadata = _record_metadata(record)
        sequence = metadata.get("sequence")
        if not isinstance(sequence, Mapping):
            output.append(record)
            continue
        arm = record.arm if isinstance(record, SessionRecord) else str(record.get("arm", ""))
        key = _session_key(sequence, arm)
        annotations = label_set.labels.get(key)
        if annotations is None:
            output.append(record)
            continue
        matched_sessions.add(key)
        events = metadata.get("memory_events", ())
        if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
            raise TypeError(f"record {key!r} memory_events must be a sequence")
        labelled_events = apply_oracle_labels(events, annotations)
        new_metadata = {**dict(metadata), "memory_events": [dict(event) for event in labelled_events]}
        if isinstance(record, SessionRecord):
            output.append(replace(record, metadata=new_metadata))
        else:
            output.append({**dict(record), "metadata": new_metadata})
    missing_sessions = sorted(set(label_set.labels) - matched_sessions)
    if missing_sessions:
        raise ValueError(f"oracle labels reference absent record sessions: {missing_sessions}")
    return tuple(output)
