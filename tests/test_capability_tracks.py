import json
from pathlib import Path

import pytest

from harness.capabilities import (
    MAX_ARTIFACT_BYTES,
    load_artifact,
    load_manifest,
    qualification_subset,
    score_artifact,
)
from harness.lifecycle import (
    LifecycleIngestReport,
    load_lifecycle_artifact,
    load_lifecycle_manifest,
    score_lifecycle_artifact,
    run_lifecycle_ingest,
    source_sha256,
    supports_lifecycle_ingest,
)
from scripts.capability_verify import main

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


def _lifecycle_artifact(tmp_path, *, replay_outcome="deduplicated"):
    manifest = load_lifecycle_manifest(ROOT / "capabilities" / "lifecycle-temporal.json")
    data, events, probes = manifest
    receipts = []
    for event in events:
        receipts.append(
            LifecycleIngestReport(
                event_id=event.event_id,
                source_path=event.source_path,
                source_sha256=event.source_sha256,
                event_order=event.event_order,
                phase=event.phase,
                outcome=replay_outcome if event.phase == "replay" else "inserted",
                indexed=(False if event.phase == "replay" and replay_outcome == "deduplicated" else True),
                deduplicated=(True if event.phase == "replay" and replay_outcome == "deduplicated" else False),
                completion_boundary="returned",
                visibility_boundary="search_verified",
            ).to_dict()
        )
    rows = []
    for probe in probes:
        for phase in ("initial", "replay"):
            ranked = [probe["expected_source_path"]]
            rows.append(
                {
                    "probe_id": probe["probe_id"],
                    "phase": phase,
                    "answer_text": probe["expected_terms"][0],
                    "ranked_source_paths": ranked,
                }
            )
    header = {
        "artifact_type": "amb-lifecycle-results",
        "schema_version": 1,
        "track": "lifecycle-temporal",
        "manifest_digest": data["manifest_digest"],
        "system": "test-fixture",
        "ingest_events": receipts,
    }
    path = tmp_path / "lifecycle.jsonl"
    path.write_text(
        "\n".join(json.dumps(item, sort_keys=True) for item in [header, *rows]) + "\n",
        encoding="utf-8",
    )
    return path, manifest


def test_lifecycle_manifest_binds_event_hashes_and_order():
    data, events, probes = load_lifecycle_manifest(ROOT / "capabilities" / "lifecycle-temporal.json")
    assert data["track"] == "lifecycle-temporal"
    assert [event.event_id for event in events] == [
        "initial-p01",
        "initial-p02",
        "initial-p03",
        "replay-p01",
    ]
    assert events[-1].source_sha256 == source_sha256(
        (ROOT / "corpus" / "sessions" / "xs-evolve-lease" / "p01.jsonl").read_bytes()
    )
    assert len(probes) == 3


def test_deduplicated_replay_is_idempotent_but_not_stale_resolution(tmp_path):
    """Mutation proof target: treating every replay as freshly indexed would claim a deduplicated
    repeat demonstrated stale candidate resolution. The report must keep that field inapplicable."""

    artifact, manifest = _lifecycle_artifact(tmp_path)
    header, rows = load_lifecycle_artifact(artifact, manifest)
    report = score_lifecycle_artifact(manifest, header, rows)
    assert report["qualification"]["passed"] is True
    assert report["qualification"]["replay_deduplicated"] is True
    assert report["qualification"]["stale_candidate_resolution"] is None
    assert report["metrics"]["replay_temporal_stability"] is None


def test_actual_replay_must_preserve_all_three_temporal_answers(tmp_path):
    """Mutation proof target: if replay rows are not scored, changing the replay current answer to
    the old p01 source would still pass. The source level replay result must fail."""

    artifact, manifest = _lifecycle_artifact(
        tmp_path,
        replay_outcome="updated",
    )
    header, rows = load_lifecycle_artifact(artifact, manifest)
    rows = tuple(
        {**row, "ranked_source_paths": ["sessions/xs-evolve-lease/p01.jsonl"]}
        if row["phase"] == "replay" and row["probe_id"] == "temporal-current-revision"
        else row
        for row in rows
    )
    report = score_lifecycle_artifact(manifest, header, rows)
    assert report["qualification"]["passed"] is False
    assert report["qualification"]["stale_candidate_resolution"] is False


def test_existing_adapters_do_not_claim_optional_lifecycle_support(tmp_path):
    from adapters.fs_grep.adapter import FsGrepAdapter

    prompt = tmp_path / "prompt.md"
    prompt.write_text("# prompt\n", encoding="utf-8")
    assert supports_lifecycle_ingest(FsGrepAdapter(tmp_path / "staging", prompt)) is False


def test_lifecycle_runner_preserves_event_order_and_hashes(tmp_path):
    """The runner is the lifecycle boundary: the adapter receives committed event order and the
    exact source hash for each event rather than relying on filesystem order."""

    _, events, _ = load_lifecycle_manifest(ROOT / "capabilities" / "lifecycle-temporal.json")

    class FakeLifecycleAdapter:
        def __init__(self):
            self.seen = []

        def ingest_event(self, namespace, event, content):
            self.seen.append((namespace, event.event_id, source_sha256(content)))
            deduplicated = event.phase == "replay"
            return LifecycleIngestReport(
                event_id=event.event_id,
                source_path=event.source_path,
                source_sha256=event.source_sha256,
                event_order=event.event_order,
                phase=event.phase,
                outcome="deduplicated" if deduplicated else "inserted",
                indexed=not deduplicated,
                deduplicated=deduplicated,
                completion_boundary="returned",
                visibility_boundary="search_verified",
            )

    adapter = FakeLifecycleAdapter()
    reports = run_lifecycle_ingest(adapter, "ns", ROOT / "corpus", events)
    assert reports is not None
    assert [event_id for _, event_id, _ in adapter.seen] == [
        "initial-p01",
        "initial-p02",
        "initial-p03",
        "replay-p01",
    ]
    assert reports[-1].outcome == "deduplicated"
