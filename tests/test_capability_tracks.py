import json
from pathlib import Path

import pytest

from scripts.capability_verify import main

from harness.capabilities import (
    MAX_ARTIFACT_BYTES,
    load_artifact,
    load_manifest,
    qualification_subset,
    score_artifact,
)


ROOT = Path(__file__).parents[1]


def _artifact(manifest, rows, path):
    header = {
        "artifact_type": "amb-capability-results",
        "schema_version": 1,
        "track": manifest.track,
        "manifest_digest": manifest.digest,
        "system": "test-fixture",
    }
    path.write_text(
        "\n".join(json.dumps(item, sort_keys=True) for item in [header, *rows]) + "\n",
        encoding="utf-8",
    )


def test_temporal_manifest_is_derived_from_existing_synthesis():
    manifest = load_manifest(ROOT / "capabilities" / "temporal.json")
    assert manifest.data["basis"]["task_id"] == "xs-evolve-lease"
    assert [probe["expected_precursor"] for probe in manifest.probes] == ["p01", "p02", "p03"]
    assert manifest.digest == manifest.data["manifest_digest"]


def test_temporal_perfect_artifact_passes_and_future_revision_fails(tmp_path):
    manifest = load_manifest(ROOT / "capabilities" / "temporal.json")
    rows = [
        {
            "probe_id": probe["probe_id"],
            "answer_text": probe["expected_terms"][0],
            "ranked_source_paths": [probe["expected_source_path"]],
        }
        for probe in manifest.probes
    ]
    artifact = tmp_path / "temporal.jsonl"
    _artifact(manifest, rows, artifact)
    _, loaded = load_artifact(artifact, manifest)
    report = score_artifact(manifest, loaded)
    assert report.qualification["passed"] is True
    assert report.metrics["temporal_hit_at_1"] == 1.0

    rows[1] = {
        **rows[1],
        "ranked_source_paths": [
            "sessions/xs-evolve-lease/p02.jsonl",
            "sessions/xs-evolve-lease/p03.jsonl",
        ],
    }
    _artifact(manifest, rows, artifact)
    _, loaded = load_artifact(artifact, manifest)
    report = score_artifact(manifest, loaded)
    assert report.qualification["passed"] is False
    assert report.metrics["future_source_ambiguity_rate"] > 0

    rows[1] = {
        **rows[1],
        "ranked_source_paths": [
            "sessions/xs-evolve-lease/p02.jsonl",
            "sessions/xs-evolve-lease/unknown.jsonl",
        ],
    }
    _artifact(manifest, rows, artifact)
    _, loaded = load_artifact(artifact, manifest)
    with pytest.raises(ValueError, match="unknown temporal sources"):
        score_artifact(manifest, loaded)


def test_isolation_manifest_has_symmetric_targeted_canaries():
    manifest = load_manifest(ROOT / "capabilities" / "isolation.json")
    tenants = {probe["tenant"] for probe in manifest.probes}
    assert tenants == {"tenant-a", "tenant-b"}
    assert all(probe["canary_document_ids"] for probe in manifest.probes)


def test_isolation_perfect_artifact_passes_and_canary_leak_fails(tmp_path):
    manifest = load_manifest(ROOT / "capabilities" / "isolation.json")
    rows = [
        {
            "probe_id": probe["probe_id"],
            "answer_text": probe["expected_terms"][0],
            "ranked_source_paths": [probe["gold_document_ids"][0]],
        }
        for probe in manifest.probes
    ]
    artifact = tmp_path / "isolation.jsonl"
    _artifact(manifest, rows, artifact)
    _, loaded = load_artifact(artifact, manifest)
    assert score_artifact(manifest, loaded).qualification["passed"] is True

    rows[0] = {
        **rows[0],
        "ranked_source_paths": ["tenant-b/targeted-canary", "tenant-a/queue-alpha-lease"],
    }
    _artifact(manifest, rows, artifact)
    _, loaded = load_artifact(artifact, manifest)
    report = score_artifact(manifest, loaded)
    assert report.qualification["passed"] is False
    assert report.metrics["canary_leak_rate"] > 0

    rows[0] = {
        **rows[0],
        "ranked_source_paths": [
            "tenant-b/targeted-canary",
            "tenant-a/queue-alpha-lease",
        ],
    }
    _artifact(manifest, rows, artifact)
    _, loaded = load_artifact(artifact, manifest)
    report = score_artifact(manifest, loaded)
    assert report.metrics["canary_leak_rate"] == 0.25

    rows[0] = {
        **rows[0],
        "ranked_source_paths": ["tenant-a/queue-alpha-lease"],
    }
    rows[2] = {
        **rows[2],
        "ranked_source_paths": [
            "tenant-a/queue-alpha-lease",
            "tenant-b/targeted-canary",
        ],
    }
    _artifact(manifest, rows, artifact)
    _, loaded = load_artifact(artifact, manifest)
    report = score_artifact(manifest, loaded)
    assert report.metrics["canary_leak_rate"] == 0.25


def test_standard_subset_is_small_and_keeps_manifest_binding():
    manifest = load_manifest(ROOT / "capabilities" / "temporal.json")
    subset = qualification_subset(
        manifest, ROOT / "capabilities" / "standard-subset-temporal.json"
    )
    assert len(subset.probes) == 3
    assert subset.digest != manifest.digest
    assert subset.data["manifest_id"].endswith("amb-temporal-standard-v1")


def test_manifest_digest_rejects_tampering(tmp_path):
    source = ROOT / "capabilities" / "isolation.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    data["documents"][0]["text"] += " changed"
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest_digest"):
        load_manifest(tampered)


def test_malformed_json_shapes_are_rejected(tmp_path):
    with pytest.raises(TypeError, match="root must be a JSON object"):
        malformed = tmp_path / "manifest.json"
        malformed.write_text("[]", encoding="utf-8")
        load_manifest(malformed)

    manifest = load_manifest(ROOT / "capabilities" / "temporal.json")
    artifact = tmp_path / "artifact.jsonl"
    artifact.write_text("[]\n", encoding="utf-8")
    with pytest.raises(TypeError, match="header must be a JSON object"):
        load_artifact(artifact, manifest)
    assert (
        main(
            [
                "--manifest",
                str(ROOT / "capabilities" / "temporal.json"),
                "--artifact",
                str(artifact),
            ]
        )
        == 2
    )


def test_duplicate_subset_ids_and_oversized_artifact_are_rejected(tmp_path):
    manifest = load_manifest(ROOT / "capabilities" / "temporal.json")
    subset = tmp_path / "subset.json"
    subset.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "subset_id": "duplicate",
                "track": "temporal",
                "manifest_id": manifest.data["manifest_id"],
                "probe_ids": [manifest.probes[0]["probe_id"]] * 2,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must be unique"):
        qualification_subset(manifest, subset)

    oversized = tmp_path / "oversized.jsonl"
    oversized.write_bytes(b" " * (MAX_ARTIFACT_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds"):
        load_artifact(oversized, manifest)
