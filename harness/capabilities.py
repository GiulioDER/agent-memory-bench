"""Small, deterministic capability tracks that sit beside the official AMB grid.

The official endpoint is execution graded. These tracks answer narrower questions that an
adapter can answer directly: which dated source was selected, and whether a tenant's answer
contains another tenant's canary. They deliberately produce a separate artifact and never alter
the preregistered task grid.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def manifest_digest(data: dict[str, Any]) -> str:
    """Hash a manifest without trusting its self-reported digest."""

    unsigned = {key: value for key, value in data.items() if key != "manifest_digest"}
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


@dataclass(frozen=True)
class CapabilityManifest:
    path: Path
    data: dict[str, Any]

    @property
    def track(self) -> str:
        return str(self.data["track"])

    @property
    def digest(self) -> str:
        return manifest_digest(self.data)

    @property
    def probes(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.data["probes"])

    def probe_map(self) -> dict[str, dict[str, Any]]:
        return {str(probe["probe_id"]): probe for probe in self.probes}


@dataclass(frozen=True)
class CapabilityReport:
    track: str
    manifest_digest: str
    probe_count: int
    metrics: dict[str, float]
    qualification: dict[str, Any]
    rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "track": self.track,
            "manifest_digest": self.manifest_digest,
            "probe_count": self.probe_count,
            "metrics": self.metrics,
            "qualification": self.qualification,
        }


def load_manifest(path: str | Path, *, repo_root: str | Path | None = None) -> CapabilityManifest:
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{manifest_path}: manifest root must be a JSON object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{manifest_path}: unsupported schema_version {data.get('schema_version')!r}")
    if not isinstance(data.get("manifest_id"), str) or not data["manifest_id"].strip():
        raise ValueError(f"{manifest_path}: manifest_id is required")
    if data.get("track") not in {"temporal", "isolation"}:
        raise ValueError(f"{manifest_path}: track must be temporal or isolation")
    if data.get("manifest_digest") != manifest_digest(data):
        raise ValueError(f"{manifest_path}: manifest_digest does not match the manifest body")
    probes = data.get("probes")
    if not isinstance(probes, list) or not probes:
        raise ValueError(f"{manifest_path}: probes must be a non-empty list")
    if any(not isinstance(probe, dict) for probe in probes):
        raise ValueError(f"{manifest_path}: every probe must be a JSON object")
    probe_ids = [probe.get("probe_id") for probe in probes]
    if any(not isinstance(probe_id, str) or not probe_id for probe_id in probe_ids):
        raise ValueError(f"{manifest_path}: every probe needs a non-empty probe_id")
    if len(set(probe_ids)) != len(probe_ids):
        raise ValueError(f"{manifest_path}: probe_id values must be unique")

    manifest = CapabilityManifest(path=manifest_path, data=data)
    root = Path(repo_root) if repo_root is not None else manifest_path.parents[1]
    if manifest.track == "temporal":
        _validate_temporal(manifest, root)
    else:
        _validate_isolation(manifest)
    return manifest


def _validate_temporal(manifest: CapabilityManifest, repo_root: Path) -> None:
    from .tasks import load_task

    basis = manifest.data.get("basis", {})
    task_id = basis.get("task_id")
    if task_id != "xs-evolve-lease":
        raise ValueError("temporal v1 must be based on xs-evolve-lease")
    task = load_task(repo_root / "tasks" / task_id)
    if task.synthesis is None or task.synthesis.shape != "evolve":
        raise ValueError("temporal basis must use the existing evolve synthesis declaration")

    shards = {shard.precursor: shard for shard in task.synthesis.shards}
    dates = {precursor: date.fromisoformat(shard.session_date) for precursor, shard in shards.items()}
    source_paths = {
        precursor: f"sessions/{task_id}/{precursor}.jsonl" for precursor in shards
    }
    corpus_manifest = repo_root / "corpus" / "manifest.json"
    corpus_sessions = json.loads(corpus_manifest.read_text(encoding="utf-8"))["sessions"]
    for precursor, source_path in source_paths.items():
        if source_path not in corpus_sessions:
            raise ValueError(f"temporal source {source_path} is absent from corpus/manifest.json")

    for probe in manifest.probes:
        reference_time = date.fromisoformat(str(probe["reference_time"]))
        expected = str(probe["expected_precursor"])
        if expected not in shards:
            raise ValueError(f"{probe['probe_id']}: expected_precursor {expected!r} is not a shard")
        effective = [
            precursor
            for precursor, when in dates.items()
            if when <= reference_time
        ]
        if not effective or effective[-1] != expected:
            raise ValueError(
                f"{probe['probe_id']}: expected_precursor is not the latest shard at reference_time"
            )
        expected_source = source_paths[expected]
        if probe.get("expected_source_path") != expected_source:
            raise ValueError(f"{probe['probe_id']}: expected_source_path does not match the shard")
        candidate_paths = probe.get("candidate_source_paths")
        if candidate_paths != [source_paths[precursor] for precursor in shards]:
            raise ValueError(f"{probe['probe_id']}: candidates must contain every dated shard")
        if not str(probe.get("query", "")).strip():
            raise ValueError(f"{probe['probe_id']}: query must be non-empty")


def _validate_isolation(manifest: CapabilityManifest) -> None:
    documents = manifest.data.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("isolation manifest needs a non-empty documents list")
    if any(not isinstance(document, dict) for document in documents):
        raise ValueError("isolation documents must be JSON objects")
    by_id = {str(document.get("document_id")): document for document in documents}
    if len(by_id) != len(documents) or "" in by_id:
        raise ValueError("isolation document_id values must be unique and non-empty")
    for document in documents:
        if not str(document.get("tenant", "")).strip():
            raise ValueError("every isolation document needs an owner tenant")
        if not str(document.get("text", "")).strip():
            raise ValueError(f"{document['document_id']}: document text must be non-empty")
    known_tenants = {str(document["tenant"]) for document in documents}
    for probe in manifest.probes:
        tenant = str(probe.get("tenant", ""))
        if tenant not in known_tenants:
            raise ValueError(f"{probe['probe_id']}: unknown tenant {tenant!r}")
        gold = [str(document_id) for document_id in probe.get("gold_document_ids", [])]
        canaries = [str(document_id) for document_id in probe.get("canary_document_ids", [])]
        if not gold or not canaries:
            raise ValueError(f"{probe['probe_id']}: gold and canary ids are required")
        if any(document_id not in by_id for document_id in gold + canaries):
            raise ValueError(f"{probe['probe_id']}: gold or canary id is not in documents")
        if any(by_id[document_id]["tenant"] != tenant for document_id in gold):
            raise ValueError(f"{probe['probe_id']}: gold documents must belong to the query tenant")
        if not any(by_id[document_id]["tenant"] != tenant for document_id in canaries):
            raise ValueError(f"{probe['probe_id']}: at least one canary must be cross tenant")
        if not str(probe.get("query", "")).strip():
            raise ValueError(f"{probe['probe_id']}: query must be non-empty")


def load_artifact(path: str | Path, manifest: CapabilityManifest) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    artifact_path = Path(path)
    if artifact_path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError(f"{artifact_path}: artifact exceeds {MAX_ARTIFACT_BYTES} bytes")
    expected = set(manifest.probe_map())
    with artifact_path.open(encoding="utf-8") as stream:
        header_line = next((line for line in stream if line.strip()), None)
        if header_line is None:
            raise ValueError(f"{artifact_path}: artifact needs a header and result rows")
        header = json.loads(header_line)
        if not isinstance(header, dict):
            raise ValueError(f"{artifact_path}: artifact header must be a JSON object")
        rows = []
        seen: set[str] = set()
        for line_number, line in enumerate(stream, start=2):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{artifact_path}:{line_number}: result row must be a JSON object")
            probe_id = row.get("probe_id")
            if not isinstance(probe_id, str) or not probe_id:
                raise ValueError(f"{artifact_path}:{line_number}: probe_id must be a non-empty string")
            if probe_id in seen:
                raise ValueError(f"{artifact_path}:{line_number}: duplicate probe_id {probe_id!r}")
            if probe_id not in expected:
                raise ValueError(f"{artifact_path}:{line_number}: unknown probe_id {probe_id!r}")
            seen.add(probe_id)
            rows.append(row)
    if header.get("artifact_type") != "amb-capability-results":
        raise ValueError(f"{artifact_path}: invalid artifact_type")
    if header.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{artifact_path}: unsupported schema_version")
    if header.get("track") != manifest.track:
        raise ValueError(f"{artifact_path}: track does not match manifest")
    if header.get("manifest_digest") != manifest.digest:
        raise ValueError(f"{artifact_path}: manifest_digest does not match manifest")
    if seen != expected:
        raise ValueError(f"{artifact_path}: exactly one result row is required for every probe")
    return header, tuple(rows)


def _row_sources(row: dict[str, Any]) -> tuple[str, ...]:
    ranked = row.get("ranked_source_paths", [])
    if not isinstance(ranked, list) or any(not isinstance(path, str) for path in ranked):
        raise ValueError(f"{row.get('probe_id')}: ranked_source_paths must be a list of strings")
    return tuple(ranked)


def score_artifact(manifest: CapabilityManifest, rows: tuple[dict[str, Any], ...]) -> CapabilityReport:
    probes = manifest.probe_map()
    by_probe = {str(row["probe_id"]): row for row in rows}
    if manifest.track == "temporal":
        metrics, qualification = _score_temporal(probes, by_probe)
    else:
        metrics, qualification = _score_isolation(manifest.data, probes, by_probe)
    return CapabilityReport(
        track=manifest.track,
        manifest_digest=manifest.digest,
        probe_count=len(rows),
        metrics=metrics,
        qualification=qualification,
        rows=rows,
    )


def _score_temporal(probes: dict[str, dict[str, Any]], rows: dict[str, dict[str, Any]]) -> tuple[dict[str, float], dict[str, Any]]:
    top_hits = []
    answer_hits = []
    future_leaks = []
    for probe_id, probe in probes.items():
        row = rows[probe_id]
        ranked = _row_sources(row)
        expected = str(probe["expected_source_path"])
        top_hits.append(bool(ranked and ranked[0] == expected))
        answer = str(row.get("answer_text", "")).lower()
        answer_hits.append(any(str(term).lower() in answer for term in probe.get("expected_terms", [])))
        candidates = probe["candidate_source_paths"]
        unknown = set(ranked) - set(candidates)
        if unknown:
            raise ValueError(f"{probe_id}: artifact cited unknown temporal sources {sorted(unknown)}")
        expected_position = candidates.index(expected)
        future_sources = set(candidates[expected_position + 1 :])
        future = [path for path in ranked if path in future_sources]
        # A future source cited anywhere in the ranked result is temporal ambiguity, even if the
        # expected source happens to be ranked first.
        future_leaks.append(bool(future))
    metrics = {
        "temporal_hit_at_1": sum(top_hits) / len(top_hits),
        "answer_term_rate": sum(answer_hits) / len(answer_hits),
        "future_source_ambiguity_rate": sum(future_leaks) / len(future_leaks),
    }
    passed = metrics["temporal_hit_at_1"] == 1.0 and metrics["answer_term_rate"] == 1.0 and metrics["future_source_ambiguity_rate"] == 0.0
    return metrics, {"passed": passed, "gates": {"top_hit": 1.0, "answer_term": 1.0, "future_ambiguity": 0.0}}


def _score_isolation(
    data: dict[str, Any], probes: dict[str, dict[str, Any]], rows: dict[str, dict[str, Any]]
) -> tuple[dict[str, float], dict[str, Any]]:
    documents = {str(document["document_id"]): document for document in data["documents"]}
    own_recall = []
    canary_leaks = []
    answer_hits = []
    for probe_id, probe in probes.items():
        row = rows[probe_id]
        ranked = set(_row_sources(row))
        unknown = ranked - documents.keys()
        if unknown:
            raise ValueError(f"{probe_id}: artifact cited unknown isolation documents {sorted(unknown)}")
        foreign = {document_id for document_id in ranked if documents[document_id]["tenant"] != probe["tenant"]}
        gold = set(probe["gold_document_ids"])
        own_recall.append(bool(ranked & gold))
        canary_leaks.append(bool(foreign))
        answer = str(row.get("answer_text", "")).lower()
        answer_hits.append(any(str(term).lower() in answer for term in probe.get("expected_terms", [])))
    metrics = {
        "own_tenant_recall": sum(own_recall) / len(own_recall),
        "canary_leak_rate": sum(canary_leaks) / len(canary_leaks),
        "answer_term_rate": sum(answer_hits) / len(answer_hits),
    }
    passed = metrics["own_tenant_recall"] == 1.0 and metrics["answer_term_rate"] == 1.0 and metrics["canary_leak_rate"] == 0.0
    return metrics, {"passed": passed, "gates": {"own_tenant_recall": 1.0, "answer_term": 1.0, "canary_leak_rate": 0.0}}


def qualification_subset(manifest: CapabilityManifest, subset_path: str | Path) -> CapabilityManifest:
    subset = json.loads(Path(subset_path).read_text(encoding="utf-8"))
    if not isinstance(subset, dict):
        raise ValueError("standard subset root must be a JSON object")
    if subset.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported standard subset schema_version")
    if subset.get("track") != manifest.track:
        raise ValueError("standard subset track does not match manifest")
    if subset.get("manifest_id") != manifest.data["manifest_id"]:
        raise ValueError("standard subset is bound to a different manifest")
    raw_selected = subset.get("probe_ids")
    if not isinstance(raw_selected, list) or not raw_selected:
        raise ValueError("standard subset must select known, non-empty probe ids")
    if any(not isinstance(probe_id, str) or not probe_id for probe_id in raw_selected):
        raise ValueError("standard subset probe_ids must be non-empty strings")
    if len(set(raw_selected)) != len(raw_selected):
        raise ValueError("standard subset probe_ids must be unique")
    selected = set(raw_selected)
    known = set(manifest.probe_map())
    if not selected or not selected <= known:
        raise ValueError("standard subset must select known, non-empty probe ids")
    data = dict(manifest.data)
    data["probes"] = [probe for probe in manifest.probes if probe["probe_id"] in selected]
    data["manifest_id"] = f"{manifest.data['manifest_id']}::{subset['subset_id']}"
    data["manifest_digest"] = manifest_digest(data)
    return CapabilityManifest(path=manifest.path, data=data)
