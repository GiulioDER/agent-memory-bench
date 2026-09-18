"""Run a live, vendor neutral smoke of the lifecycle temporal capability."""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

from harness.lifecycle import (
    LifecycleEvent,
    LifecycleIngestReport,
    load_lifecycle_artifact,
    load_lifecycle_manifest,
    run_lifecycle_ingest,
    score_lifecycle_artifact,
    source_sha256,
)

ROOT = Path(__file__).resolve().parents[1]


class ReferenceReplayAdapter:
    """A deterministic in memory adapter used only to exercise the lifecycle harness."""

    def __init__(self) -> None:
        self.records: dict[str, tuple[str, date]] = {}

    def ingest_event(
        self, namespace: str, event: LifecycleEvent, content: bytes
    ) -> LifecycleIngestReport:
        del namespace
        digest = source_sha256(content)
        existing = self.records.get(event.source_path)
        if existing is None:
            outcome = "inserted"
            indexed = True
            deduplicated = False
            self.records[event.source_path] = (digest, date.fromisoformat(event.authored_at))
        else:
            if existing[0] != digest:
                raise ValueError(f"source changed during replay: {event.source_path}")
            # Exercise the actual replay branch. The source is indexed again, but its authored
            # date remains the date in the event rather than the replay time.
            outcome = "updated"
            indexed = True
            deduplicated = False
            self.records[event.source_path] = (digest, existing[1])
        return LifecycleIngestReport(
            event_id=event.event_id,
            source_path=event.source_path,
            source_sha256=digest,
            event_order=event.event_order,
            phase=event.phase,
            outcome=outcome,
            indexed=indexed,
            deduplicated=deduplicated,
            completion_boundary="returned after durable write",
            visibility_boundary="reference search reads committed record",
            items_stored=len(self.records),
        )

    def search(self, probe: dict) -> str:
        reference = date.fromisoformat(probe["reference_time"])
        eligible = [
            (authored, path)
            for path, (_, authored) in self.records.items()
            if authored <= reference
        ]
        if not eligible:
            raise RuntimeError(f"no source is eligible for {probe['probe_id']}")
        return max(eligible)[1]


def main() -> int:
    manifest = load_lifecycle_manifest(ROOT / "capabilities" / "lifecycle-temporal.json")
    data, events, probes = manifest
    adapter = ReferenceReplayAdapter()
    receipts = run_lifecycle_ingest(adapter, "lifecycle-smoke", ROOT / "corpus", events)
    if receipts is None:
        raise RuntimeError("reference adapter unexpectedly lacks lifecycle support")

    rows = []
    for phase in ("initial", "replay"):
        for probe in probes:
            rows.append(
                {
                    "probe_id": probe["probe_id"],
                    "phase": phase,
                    "answer_text": probe["expected_terms"][0],
                    "ranked_source_paths": [adapter.search(probe)],
                }
            )
    header = {
        "artifact_type": "amb-lifecycle-results",
        "schema_version": 1,
        "track": "lifecycle-temporal",
        "manifest_digest": data["manifest_digest"],
        "system": "reference-replay-smoke",
        "ingest_events": [receipt.to_dict() for receipt in receipts],
    }
    with tempfile.TemporaryDirectory(prefix="amb-lifecycle-smoke-") as temporary:
        artifact = Path(temporary) / "lifecycle.jsonl"
        artifact.write_text(
            "\n".join(json.dumps(item, sort_keys=True) for item in [header, *rows]) + "\n",
            encoding="utf-8",
        )
        loaded_header, loaded_rows = load_lifecycle_artifact(artifact, manifest)
        report = score_lifecycle_artifact(manifest, loaded_header, loaded_rows)

    if not report["qualification"]["passed"]:
        raise RuntimeError(json.dumps(report, indent=2, sort_keys=True))
    if report["qualification"]["replay_outcome"] != "updated":
        raise RuntimeError("smoke did not exercise an actual source replay")
    if report["qualification"]["stale_candidate_resolution"] is not True:
        raise RuntimeError("smoke did not preserve temporal answers after source replay")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
