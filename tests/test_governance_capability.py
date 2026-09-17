from __future__ import annotations

import json
from pathlib import Path

from harness.governance import load_artifact, load_manifest, score_artifact

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "capabilities" / "governance.json"


def _artifact(tmp_path: Path):
    manifest = load_manifest(MANIFEST_PATH)
    rows = []
    for probe in manifest.probes:
        rows.append(
            {
                "probe_id": probe["probe_id"],
                "decision": probe["expected_decision"],
                "candidate_finding_ids": list(
                    dict.fromkeys(
                        probe["replacement_candidate_ids"] + probe["nonreplacement_finding_ids"]
                    )
                ),
                "selected_finding_ids": list(probe["expected_selected_finding_ids"]),
                "conflict_finding_ids": list(probe["expected_conflict_finding_ids"]),
                "answer_text": " ".join(probe["expected_terms"]),
            }
        )
    header = {
        "artifact_type": "amb-governance-results",
        "schema_version": 1,
        "track": "governance",
        "manifest_digest": manifest.digest,
        "system": "test-fixture",
    }
    path = tmp_path / "governance.jsonl"
    path.write_text(
        "\n".join(json.dumps(item, sort_keys=True) for item in [header, *rows]) + "\n",
        encoding="utf-8",
    )
    return path, manifest


def test_governance_manifest_and_reference_artifact_pass(tmp_path):
    artifact, manifest = _artifact(tmp_path)
    _, rows = load_artifact(artifact, manifest)
    report = score_artifact(manifest, rows)
    assert report.qualification["passed"] is True
    assert report.metrics["decision_accuracy"] == 1.0
    assert report.metrics["replacement_candidate_recall"] == 1.0
    assert report.metrics["safe_application_rate"] == 1.0


def test_wrong_successor_is_not_hidden_by_correct_candidate_recall(tmp_path):
    """Mutation proof target: finding the old and new candidates is not enough if the old one is applied."""
    artifact, manifest = _artifact(tmp_path)
    _, rows = load_artifact(artifact, manifest)
    mutated = tuple(
        {
            **row,
            "selected_finding_ids": ["finding-alpha-lease-v1"],
        }
        if row["probe_id"] == "governance-current-supersession"
        else row
        for row in rows
    )
    report = score_artifact(manifest, mutated)
    assert report.qualification["passed"] is False
    assert report.metrics["replacement_candidate_recall"] == 1.0
    assert report.metrics["decision_accuracy"] < 1.0


def test_adjacent_finding_cannot_be_selected_as_applicable(tmp_path):
    """Mutation proof target: a relevant looking adjacent note must not become an applied answer."""
    artifact, manifest = _artifact(tmp_path)
    _, rows = load_artifact(artifact, manifest)
    mutated = tuple(
        {
            **row,
            "selected_finding_ids": ["finding-alpha-lease-staging"],
        }
        if row["probe_id"] == "governance-adjacent-environment"
        else row
        for row in rows
    )
    report = score_artifact(manifest, mutated)
    assert report.qualification["passed"] is False
    assert report.metrics["safe_application_rate"] < 1.0


def test_conflict_requires_both_same_scope_findings(tmp_path):
    """Mutation proof target: silently choosing one side must fail conflict qualification."""
    artifact, manifest = _artifact(tmp_path)
    _, rows = load_artifact(artifact, manifest)
    mutated = tuple(
        {
            **row,
            "decision": "apply",
            "selected_finding_ids": ["finding-export-order-a"],
            "conflict_finding_ids": [],
        }
        if row["probe_id"] == "governance-same-scope-conflict"
        else row
        for row in rows
    )
    report = score_artifact(manifest, mutated)
    assert report.qualification["passed"] is False
    assert report.metrics["conflict_identification_rate"] < 1.0
