"""Optional source level ingestion for lifecycle capability fixtures.

The ordinary :class:`MemoryAdapter` contract is intentionally whole corpus oriented.  A product
that wants to participate in a lifecycle fixture must additionally implement ``ingest_event``
with the protocol below.  Keeping this surface optional lets adapters that rebuild, verify out of
band, or otherwise cannot replay one source report ``unsupported`` rather than a misleading score.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from .capabilities import load_manifest, manifest_digest
from .adapters.base import resolve_corpus_path

LIFECYCLE_SCHEMA_VERSION = 1
LIFECYCLE_TRACK = "lifecycle-temporal"
LIFECYCLE_OUTCOMES = frozenset({"inserted", "updated", "deduplicated", "rebuilt", "unknown"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PHASES = frozenset({"initial", "replay"})


@dataclass(frozen=True)
class LifecycleEvent:
    """One ordered source event offered to an optional lifecycle adapter."""

    event_id: str
    source_path: str
    source_sha256: str
    event_order: int
    phase: Literal["initial", "replay"]
    authored_at: str
    replay_of: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "event_order": self.event_order,
            "phase": self.phase,
            "authored_at": self.authored_at,
            "replay_of": self.replay_of,
        }


@dataclass(frozen=True)
class LifecycleIngestReport:
    """The adapter's receipt for one lifecycle event.

    ``completion_boundary`` says when the adapter considered the write complete.  The separate
    ``visibility_boundary`` says what proves a subsequent fresh session could see it.  These are
    deliberately descriptive, adapter supplied values; the verifier rejects an empty or unknown
    boundary instead of treating a return value alone as visibility proof.
    """

    event_id: str
    source_path: str
    source_sha256: str
    event_order: int
    phase: Literal["initial", "replay"]
    outcome: str
    indexed: bool | None
    deduplicated: bool | None
    completion_boundary: str
    visibility_boundary: str
    items_stored: int | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "event_order": self.event_order,
            "phase": self.phase,
            "outcome": self.outcome,
            "indexed": self.indexed,
            "deduplicated": self.deduplicated,
            "completion_boundary": self.completion_boundary,
            "visibility_boundary": self.visibility_boundary,
            "items_stored": self.items_stored,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> LifecycleIngestReport:
        notes = value.get("notes", ())
        if not isinstance(notes, list | tuple) or any(not isinstance(item, str) for item in notes):
            raise ValueError("lifecycle receipt notes must be strings")
        return cls(
            event_id=str(value.get("event_id", "")),
            source_path=str(value.get("source_path", "")),
            source_sha256=str(value.get("source_sha256", "")),
            event_order=int(value.get("event_order", 0)),
            phase=value.get("phase", "unknown"),
            outcome=str(value.get("outcome", "")),
            indexed=value.get("indexed"),
            deduplicated=value.get("deduplicated"),
            completion_boundary=str(value.get("completion_boundary", "")),
            visibility_boundary=str(value.get("visibility_boundary", "")),
            items_stored=value.get("items_stored"),
            notes=tuple(notes),
        )

    def validate_for(self, event: LifecycleEvent) -> None:
        """Refuse a receipt that does not describe the event it claims to process."""

        if (
            self.event_id,
            self.source_path,
            self.source_sha256,
            self.event_order,
            self.phase,
        ) != (
            event.event_id,
            event.source_path,
            event.source_sha256,
            event.event_order,
            event.phase,
        ):
            raise ValueError(f"lifecycle receipt does not match event {event.event_id!r}")
        if self.outcome not in LIFECYCLE_OUTCOMES:
            raise ValueError(f"{event.event_id}: unknown lifecycle outcome {self.outcome!r}")
        if not isinstance(self.indexed, bool | type(None)):
            raise ValueError(f"{event.event_id}: indexed must be true, false, or null")
        if not isinstance(self.deduplicated, bool | type(None)):
            raise ValueError(f"{event.event_id}: deduplicated must be true, false, or null")
        if not self.completion_boundary.strip():
            raise ValueError(f"{event.event_id}: completion_boundary is required")
        if not self.visibility_boundary.strip():
            raise ValueError(f"{event.event_id}: visibility_boundary is required")
        if self.outcome == "deduplicated" and (self.deduplicated is not True or self.indexed is True):
            raise ValueError(f"{event.event_id}: deduplicated must not claim a fresh index")
        if self.outcome in {"inserted", "updated", "rebuilt"} and self.indexed is not True:
            raise ValueError(f"{event.event_id}: {self.outcome} must claim indexed=true")


@runtime_checkable
class LifecycleIngestCapability(Protocol):
    """Optional adapter surface for one source event at a time."""

    def ingest_event(
        self, namespace: str, event: LifecycleEvent, content: bytes
    ) -> LifecycleIngestReport:
        """Ingest exactly ``event`` and return its completion and visibility receipt."""


def supports_lifecycle_ingest(adapter: object) -> bool:
    """Return whether an adapter exposes the optional source event method."""

    return isinstance(adapter, LifecycleIngestCapability)


def run_lifecycle_ingest(
    adapter: object,
    namespace: str,
    corpus_root: str | Path,
    events: Sequence[LifecycleEvent],
) -> tuple[LifecycleIngestReport, ...] | None:
    """Drive an opted in adapter through ``events`` and validate every returned receipt.

    ``None`` is the explicit unsupported result. The helper reads each source once, checks the
    committed hash before handing bytes to the adapter, and refuses to continue after an event
    reports a mismatched identity or incomplete visibility boundary.
    """

    if not supports_lifecycle_ingest(adapter):
        return None
    root = Path(corpus_root)
    reports: list[LifecycleIngestReport] = []
    for event in events:
        content = resolve_corpus_path(root, event.source_path).read_bytes()
        if source_sha256(content) != event.source_sha256:
            raise ValueError(f"{event.event_id}: source bytes do not match the lifecycle manifest")
        report = adapter.ingest_event(namespace, event, content)
        if not isinstance(report, LifecycleIngestReport):
            raise TypeError(f"{event.event_id}: ingest_event must return LifecycleIngestReport")
        report.validate_for(event)
        reports.append(report)
    return tuple(reports)


def load_lifecycle_manifest(
    path: str | Path, *, repo_root: str | Path | None = None
) -> tuple[dict[str, Any], tuple[LifecycleEvent, ...], tuple[dict[str, Any], ...]]:
    """Load and validate the committed ``xs-evolve-lease`` lifecycle manifest."""

    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{manifest_path}: manifest root must be a JSON object")
    if data.get("schema_version") != LIFECYCLE_SCHEMA_VERSION:
        raise ValueError(f"{manifest_path}: unsupported schema_version")
    if data.get("track") != LIFECYCLE_TRACK:
        raise ValueError(f"{manifest_path}: track must be {LIFECYCLE_TRACK!r}")
    if data.get("manifest_digest") != manifest_digest(data):
        raise ValueError(f"{manifest_path}: manifest_digest does not match the manifest body")

    root = Path(repo_root) if repo_root is not None else manifest_path.parents[1]
    temporal_path = root / "capabilities" / str(data.get("temporal_manifest", "temporal.json"))
    temporal_manifest = load_manifest(temporal_path, repo_root=root)
    temporal = temporal_manifest.data
    if temporal.get("track") != "temporal":
        raise ValueError("lifecycle manifest must reference the temporal capability manifest")
    if data.get("temporal_manifest_digest") != temporal_manifest.digest:
        raise ValueError("lifecycle manifest is bound to a different temporal manifest")

    corpus_sessions = json.loads((root / "corpus" / "manifest.json").read_text(encoding="utf-8"))["sessions"]
    if not isinstance(corpus_sessions, dict):
        raise ValueError("corpus manifest sessions must be an object")

    raw_events = data.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("lifecycle manifest needs a non empty events list")
    events = tuple(_event_from_dict(item) for item in raw_events)
    if [event.event_order for event in events] != list(range(1, len(events) + 1)):
        raise ValueError("lifecycle event_order must be contiguous and start at one")
    if [event.phase for event in events] != ["initial", "initial", "initial", "replay"]:
        raise ValueError("xs-evolve-lease lifecycle events must be three initial events then one replay")
    if len({event.event_id for event in events}) != len(events):
        raise ValueError("lifecycle event_id values must be unique")
    if events[-1].source_path != events[0].source_path or events[-1].replay_of != events[0].event_id:
        raise ValueError("the replay event must repeat initial-p01 exactly")

    for event in events:
        if not _SHA256.fullmatch(event.source_sha256):
            raise ValueError(f"{event.event_id}: source_sha256 must be a lowercase sha256")
        if corpus_sessions.get(event.source_path) != event.source_sha256:
            raise ValueError(f"{event.event_id}: source hash does not match corpus/manifest.json")
        date.fromisoformat(event.authored_at)

    probe_ids = data.get("probe_ids")
    temporal_probes = tuple(temporal.get("probes", ()))
    known = {str(probe.get("probe_id")) for probe in temporal_probes}
    if not isinstance(probe_ids, list) or len(probe_ids) != len(known) or set(probe_ids) != known:
        raise ValueError("lifecycle probe_ids must select every temporal probe exactly once")
    return data, events, temporal_probes


def _event_from_dict(value: Any) -> LifecycleEvent:
    if not isinstance(value, dict):
        raise TypeError("every lifecycle event must be an object")
    phase = value.get("phase")
    if phase not in _PHASES:
        raise ValueError(f"unknown lifecycle phase {phase!r}")
    return LifecycleEvent(
        event_id=str(value.get("event_id", "")),
        source_path=str(value.get("source_path", "")),
        source_sha256=str(value.get("source_sha256", "")),
        event_order=int(value.get("event_order", 0)),
        phase=phase,
        authored_at=str(value.get("authored_at", "")),
        replay_of=value.get("replay_of"),
    )


def load_lifecycle_artifact(
    path: str | Path,
    manifest: tuple[dict[str, Any], tuple[LifecycleEvent, ...], tuple[dict[str, Any], ...]],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Load a JSONL lifecycle artifact and validate its event receipts and result rows."""

    _, events, probes = manifest
    stream = Path(path).open(encoding="utf-8")
    with stream:
        lines = [line for line in stream if line.strip()]
    if not lines:
        raise ValueError(f"{path}: lifecycle artifact is empty")
    header = json.loads(lines[0])
    if not isinstance(header, dict):
        raise TypeError("lifecycle artifact header must be an object")
    if header.get("artifact_type") != "amb-lifecycle-results":
        raise ValueError("invalid lifecycle artifact_type")
    if header.get("schema_version") != LIFECYCLE_SCHEMA_VERSION:
        raise ValueError("unsupported lifecycle artifact schema_version")
    if header.get("manifest_digest") != manifest_digest(manifest[0]):
        raise ValueError("lifecycle artifact manifest_digest does not match manifest")

    raw_receipts = header.get("ingest_events")
    if not isinstance(raw_receipts, list) or len(raw_receipts) != len(events):
        raise ValueError("lifecycle artifact needs one ingest receipt per event")
    receipts = [LifecycleIngestReport.from_dict(item) for item in raw_receipts]
    by_event = {event.event_id: event for event in events}
    if {receipt.event_id for receipt in receipts} != set(by_event):
        raise ValueError("lifecycle receipts must cover every manifest event exactly once")
    for receipt in receipts:
        receipt.validate_for(by_event[receipt.event_id])

    expected = {(str(probe["probe_id"]), phase) for probe in probes for phase in _PHASES}
    rows = []
    seen: set[tuple[str, str]] = set()
    for line_number, line in enumerate(lines[1:], start=2):
        row = json.loads(line)
        if not isinstance(row, dict):
            raise TypeError(f"{path}:{line_number}: lifecycle result must be an object")
        key = (str(row.get("probe_id", "")), str(row.get("phase", "")))
        if key not in expected:
            raise ValueError(f"{path}:{line_number}: unknown lifecycle result key {key!r}")
        if key in seen:
            raise ValueError(f"{path}:{line_number}: duplicate lifecycle result {key!r}")
        if not isinstance(row.get("ranked_source_paths", []), list):
            raise ValueError(f"{path}:{line_number}: ranked_source_paths must be a list")
        seen.add(key)
        rows.append(row)
    if seen != expected:
        raise ValueError("lifecycle artifact needs one result row per probe and phase")
    return header, tuple(rows)


def score_lifecycle_artifact(
    manifest: tuple[dict[str, Any], tuple[LifecycleEvent, ...], tuple[dict[str, Any], ...]],
    header: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Score initial temporal behavior, replay idempotence, and replay stability separately."""

    _, events, probes = manifest
    probe_by_id = {str(probe["probe_id"]): probe for probe in probes}
    row_by_key = {(str(row["probe_id"]), str(row["phase"])): row for row in rows}
    phase_reports = {phase: _score_phase(probe_by_id, row_by_key, phase) for phase in _PHASES}
    receipts = [LifecycleIngestReport.from_dict(item) for item in header["ingest_events"]]
    replay = next(receipt for receipt in receipts if receipt.phase == "replay")
    contract_valid = all(
        receipt.completion_boundary.lower() != "unknown"
        and receipt.visibility_boundary.lower() != "unknown"
        for receipt in receipts
    )
    replay_deduplicated = replay.outcome == "deduplicated" and replay.deduplicated is True
    actual_source_replay = (
        replay.outcome in {"inserted", "updated"}
        and replay.indexed is True
        and replay.deduplicated is False
    )
    replay_stability = (
        phase_reports["replay"]["passed"] if actual_source_replay else None
    )
    passed = bool(
        contract_valid
        and phase_reports["initial"]["passed"]
        and (replay_deduplicated or (actual_source_replay and replay_stability))
    )
    return {
        "track": LIFECYCLE_TRACK,
        "manifest_digest": manifest_digest(manifest[0]),
        "metrics": {
            "initial_temporal_hit_at_1": phase_reports["initial"]["temporal_hit_at_1"],
            "replay_temporal_hit_at_1": phase_reports["replay"]["temporal_hit_at_1"],
            "initial_answer_term_rate": phase_reports["initial"]["answer_term_rate"],
            "replay_answer_term_rate": phase_reports["replay"]["answer_term_rate"],
            "initial_future_source_ambiguity_rate": phase_reports["initial"]["future_source_ambiguity_rate"],
            "replay_future_source_ambiguity_rate": phase_reports["replay"]["future_source_ambiguity_rate"],
            "replay_idempotence": float(replay_deduplicated),
            "replay_temporal_stability": replay_stability,
        },
        "qualification": {
            "passed": passed,
            "contract_valid": contract_valid,
            "replay_outcome": replay.outcome,
            "replay_deduplicated": replay_deduplicated,
            "actual_source_replay": actual_source_replay,
            "stale_candidate_resolution": replay_stability,
            "note": (
                "deduplicated replay proves idempotence only; it does not qualify as a newly indexed "
                "stale candidate resolution"
            ),
        },
    }


def _score_phase(
    probes: Mapping[str, Mapping[str, Any]],
    rows: Mapping[tuple[str, str], Mapping[str, Any]],
    phase: str,
) -> dict[str, Any]:
    top_hits: list[bool] = []
    answer_hits: list[bool] = []
    future_leaks: list[bool] = []
    for probe_id, probe in probes.items():
        row = rows[(probe_id, phase)]
        ranked = row["ranked_source_paths"]
        if any(not isinstance(path, str) for path in ranked):
            raise ValueError(f"{probe_id}/{phase}: ranked_source_paths must contain strings")
        candidates = probe["candidate_source_paths"]
        expected = probe["expected_source_path"]
        unknown = set(ranked) - set(candidates)
        if unknown:
            raise ValueError(f"{probe_id}/{phase}: unknown temporal sources {sorted(unknown)}")
        top_hits.append(bool(ranked and ranked[0] == expected))
        answer = str(row.get("answer_text", "")).lower()
        answer_hits.append(any(str(term).lower() in answer for term in probe.get("expected_terms", [])))
        expected_position = candidates.index(expected)
        future_sources = set(candidates[expected_position + 1 :])
        future_leaks.append(any(path in future_sources for path in ranked))
    hit_rate = sum(top_hits) / len(top_hits)
    answer_rate = sum(answer_hits) / len(answer_hits)
    ambiguity = sum(future_leaks) / len(future_leaks)
    return {
        "temporal_hit_at_1": hit_rate,
        "answer_term_rate": answer_rate,
        "future_source_ambiguity_rate": ambiguity,
        "passed": hit_rate == 1.0 and answer_rate == 1.0 and ambiguity == 0.0,
    }


def source_sha256(content: bytes) -> str:
    """Return the canonical digest adapters must report for event content."""

    return hashlib.sha256(content).hexdigest()
