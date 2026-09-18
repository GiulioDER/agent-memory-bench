"""Applicability and replacement eligibility capability track.

This track is deliberately separate from the official execution endpoint. It asks a memory
system to expose stable finding ids, the candidates it considered, and the decision it made.
The verifier then checks applicability, supersession, conflict handling, and safe abstention
without using an LLM judge.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
TRACK = "governance"
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
DECISIONS = frozenset({"apply", "conflict", "not_applicable"})


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def manifest_digest(data: dict[str, Any]) -> str:
    """Hash a manifest without trusting its self reported digest."""

    unsigned = {key: value for key, value in data.items() if key != "manifest_digest"}
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


@dataclass(frozen=True)
class GovernanceManifest:
    path: Path
    data: dict[str, Any]

    @property
    def digest(self) -> str:
        return manifest_digest(self.data)

    @property
    def findings(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.data["findings"])

    @property
    def probes(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.data["probes"])

    def finding_map(self) -> dict[str, dict[str, Any]]:
        return {str(finding["finding_id"]): finding for finding in self.findings}

    def probe_map(self) -> dict[str, dict[str, Any]]:
        return {str(probe["probe_id"]): probe for probe in self.probes}


@dataclass(frozen=True)
class GovernanceReport:
    manifest_digest: str
    probe_count: int
    metrics: dict[str, float]
    qualification: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "track": TRACK,
            "manifest_digest": self.manifest_digest,
            "probe_count": self.probe_count,
            "metrics": self.metrics,
            "qualification": self.qualification,
        }


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{label} must be a list of non empty strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{label} must not contain duplicates")
    return value


def load_manifest(path: str | Path) -> GovernanceManifest:
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{manifest_path}: manifest root must be an object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{manifest_path}: unsupported schema_version")
    if data.get("track") != TRACK:
        raise ValueError(f"{manifest_path}: track must be {TRACK!r}")
    if not isinstance(data.get("manifest_id"), str) or not data["manifest_id"].strip():
        raise ValueError(f"{manifest_path}: manifest_id is required")
    if data.get("manifest_digest") != manifest_digest(data):
        raise ValueError(f"{manifest_path}: manifest_digest does not match the manifest body")

    findings = data.get("findings")
    if not isinstance(findings, list) or not findings:
        raise ValueError(f"{manifest_path}: findings must be a non empty list")
    by_id: dict[str, dict[str, Any]] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            raise TypeError("governance findings must be objects")
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or not finding_id.strip() or finding_id in by_id:
            raise ValueError("governance finding_id values must be unique and non empty")
        scope = finding.get("scope")
        if not isinstance(scope, dict) or not scope:
            raise ValueError(f"{finding_id}: scope must be a non empty object")
        if any(not isinstance(key, str) or not key for key in scope):
            raise ValueError(f"{finding_id}: scope keys must be non empty strings")
        if any(not isinstance(value, str) or not value for value in scope.values()):
            raise ValueError(f"{finding_id}: scope values must be non empty strings")
        for field in ("source_path", "claim"):
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                raise ValueError(f"{finding_id}: {field} is required")
        for field in ("valid_from", "valid_until"):
            if finding.get(field) is not None:
                date.fromisoformat(str(finding[field]))
        supersedes = finding.get("supersedes", [])
        _string_list(supersedes, f"{finding_id}: supersedes")
        by_id[finding_id] = finding

    for finding_id, finding in by_id.items():
        for superseded in finding.get("supersedes", []):
            if superseded not in by_id:
                raise ValueError(f"{finding_id}: supersedes unknown finding {superseded!r}")
            if superseded == finding_id:
                raise ValueError(f"{finding_id}: a finding cannot supersede itself")

    probes = data.get("probes")
    if not isinstance(probes, list) or not probes:
        raise ValueError(f"{manifest_path}: probes must be a non empty list")
    seen: set[str] = set()
    for probe in probes:
        if not isinstance(probe, dict):
            raise TypeError("governance probes must be objects")
        probe_id = probe.get("probe_id")
        if not isinstance(probe_id, str) or not probe_id.strip() or probe_id in seen:
            raise ValueError("governance probe_id values must be unique and non empty")
        seen.add(probe_id)
        if not isinstance(probe.get("query"), str) or not probe["query"].strip():
            raise ValueError(f"{probe_id}: query is required")
        decision = probe.get("expected_decision")
        if decision not in DECISIONS:
            raise ValueError(f"{probe_id}: unsupported expected_decision {decision!r}")
        id_fields = (
            "expected_selected_finding_ids",
            "expected_conflict_finding_ids",
            "replacement_candidate_ids",
            "nonreplacement_finding_ids",
            "forbidden_selected_finding_ids",
        )
        values = {
            field: _string_list(probe.get(field, []), f"{probe_id}: {field}")
            for field in id_fields
        }
        expected_terms = _string_list(probe.get("expected_terms", []), f"{probe_id}: expected_terms")
        all_ids = set().union(*(set(value) for value in values.values()))
        unknown = all_ids - set(by_id)
        if unknown:
            raise ValueError(f"{probe_id}: unknown finding ids {sorted(unknown)}")
        selected = set(values["expected_selected_finding_ids"])
        conflict = set(values["expected_conflict_finding_ids"])
        if decision == "apply" and len(selected) != 1:
            raise ValueError(f"{probe_id}: apply requires exactly one expected selected finding")
        if decision == "conflict" and len(conflict) < 2:
            raise ValueError(f"{probe_id}: conflict requires at least two expected findings")
        if decision == "not_applicable" and (selected or conflict):
            raise ValueError(f"{probe_id}: not_applicable cannot select or resolve a conflict")
        if selected & conflict:
            raise ValueError(f"{probe_id}: selected and conflict findings must be disjoint")
        if not expected_terms:
            raise ValueError(f"{probe_id}: expected_terms must not be empty")

    return GovernanceManifest(path=manifest_path, data=data)


def _ids(row: dict[str, Any], field: str) -> tuple[str, ...]:
    values = row.get(field, [])
    if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
        raise ValueError(f"{row.get('probe_id')}: {field} must be a list of strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{row.get('probe_id')}: {field} must not contain duplicates")
    return tuple(values)


def load_artifact(path: str | Path, manifest: GovernanceManifest) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    artifact_path = Path(path)
    if artifact_path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError(f"{artifact_path}: artifact exceeds {MAX_ARTIFACT_BYTES} bytes")
    expected = set(manifest.probe_map())
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with artifact_path.open(encoding="utf-8") as stream:
        header_line = next((line for line in stream if line.strip()), None)
        if header_line is None:
            raise ValueError(f"{artifact_path}: artifact needs a header and result rows")
        header = json.loads(header_line)
        if not isinstance(header, dict):
            raise TypeError(f"{artifact_path}: artifact header must be an object")
        for line_number, line in enumerate(stream, start=2):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise TypeError(f"{artifact_path}:{line_number}: result row must be an object")
            probe_id = row.get("probe_id")
            if not isinstance(probe_id, str) or probe_id not in expected:
                raise ValueError(f"{artifact_path}:{line_number}: unknown probe_id")
            if probe_id in seen:
                raise ValueError(f"{artifact_path}:{line_number}: duplicate probe_id {probe_id!r}")
            decision = row.get("decision")
            if decision not in DECISIONS:
                raise ValueError(f"{probe_id}: unsupported decision {decision!r}")
            for field in ("candidate_finding_ids", "selected_finding_ids", "conflict_finding_ids"):
                _ids(row, field)
            row_ids = set().union(
                _ids(row, "candidate_finding_ids"),
                _ids(row, "selected_finding_ids"),
                _ids(row, "conflict_finding_ids"),
            )
            unknown = row_ids - set(manifest.finding_map())
            if unknown:
                raise ValueError(f"{probe_id}: artifact cited unknown findings {sorted(unknown)}")
            candidates = set(_ids(row, "candidate_finding_ids"))
            if not set(_ids(row, "selected_finding_ids")) <= candidates:
                raise ValueError(f"{probe_id}: selected findings must be candidates")
            if not set(_ids(row, "conflict_finding_ids")) <= candidates:
                raise ValueError(f"{probe_id}: conflict findings must be candidates")
            seen.add(probe_id)
            rows.append(row)
    if header.get("artifact_type") != "amb-governance-results":
        raise ValueError(f"{artifact_path}: invalid artifact_type")
    if header.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{artifact_path}: unsupported schema_version")
    if header.get("track") != TRACK:
        raise ValueError(f"{artifact_path}: track does not match manifest")
    if header.get("manifest_digest") != manifest.digest:
        raise ValueError(f"{artifact_path}: manifest_digest does not match manifest")
    if seen != expected:
        raise ValueError(f"{artifact_path}: exactly one result row is required for every probe")
    return header, tuple(rows)


def score_artifact(manifest: GovernanceManifest, rows: tuple[dict[str, Any], ...]) -> GovernanceReport:
    probes = manifest.probe_map()
    by_probe = {str(row["probe_id"]): row for row in rows}
    decision_hits: list[bool] = []
    candidate_hits: list[bool] = []
    safety_hits: list[bool] = []
    term_hits: list[bool] = []
    conflict_hits: list[bool] = []
    nonreplacement_hits: list[bool] = []
    pool_sizes: list[int] = []
    for probe_id, probe in probes.items():
        row = by_probe[probe_id]
        decision = row["decision"]
        selected = set(_ids(row, "selected_finding_ids"))
        conflicts = set(_ids(row, "conflict_finding_ids"))
        candidates = set(_ids(row, "candidate_finding_ids"))
        expected_selected = set(probe["expected_selected_finding_ids"])
        expected_conflict = set(probe["expected_conflict_finding_ids"])
        decision_hits.append(
            decision == probe["expected_decision"]
            and (decision != "apply" or selected == expected_selected)
            and (decision != "conflict" or conflicts == expected_conflict)
            and (decision != "not_applicable" or not selected and not conflicts)
        )
        candidate_hits.append(set(probe["replacement_candidate_ids"]) <= candidates)
        safety_hits.append(not selected.intersection(probe["forbidden_selected_finding_ids"]))
        answer = str(row.get("answer_text", "")).lower()
        term_hits.append(any(term.lower() in answer for term in probe["expected_terms"]))
        conflict_hits.append(
            probe["expected_decision"] != "conflict"
            or (decision == "conflict" and conflicts == expected_conflict)
        )
        nonreplacement_hits.append(bool(candidates.intersection(probe["nonreplacement_finding_ids"])))
        pool_sizes.append(len(candidates))

    metrics = {
        "decision_accuracy": sum(decision_hits) / len(decision_hits),
        "replacement_candidate_recall": sum(candidate_hits) / len(candidate_hits),
        "safe_application_rate": sum(safety_hits) / len(safety_hits),
        "evidence_term_rate": sum(term_hits) / len(term_hits),
        "conflict_identification_rate": sum(conflict_hits) / len(conflict_hits),
        "nonreplacement_candidate_rate": sum(nonreplacement_hits) / len(nonreplacement_hits),
        "mean_candidate_pool_size": sum(pool_sizes) / len(pool_sizes),
    }
    gates = {
        "decision_accuracy": 1.0,
        "replacement_candidate_recall": 1.0,
        "safe_application_rate": 1.0,
        "evidence_term_rate": 1.0,
    }
    passed = all(metrics[name] == threshold for name, threshold in gates.items())
    return GovernanceReport(
        manifest_digest=manifest.digest,
        probe_count=len(rows),
        metrics=metrics,
        qualification={"passed": passed, "gates": gates},
    )
