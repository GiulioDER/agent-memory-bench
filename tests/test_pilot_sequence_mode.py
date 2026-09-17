from __future__ import annotations

import asyncio
import json
import sys

from harness.frozen_manifest import FrozenEvaluationManifest
from scripts import pilot


def test_pilot_sequence_dry_run_uses_plan_roster_and_position_count(tmp_path, monkeypatch, capsys):
    """Mutation: dropping sequence reporting would hide that pilot fell back to grid mode."""

    manifest = FrozenEvaluationManifest.build(
        pilot.REPO,
        manifest_id="pilot-sequence-manifest",
        created_at="2026-09-17T12:00:00+00:00",
        corpus_files=["corpus/manifest.json"],
        protocol_files=["preregistration/084-sequence-selectivity.md"],
    )
    manifest_path = tmp_path / "manifest.json"
    manifest.write(manifest_path)
    source_prompt = json.loads(
        (pilot.REPO / "tasks" / "ts-json-sorted" / "task.json").read_text(encoding="utf-8")
    )["prompt"]
    target_prompt = json.loads(
        (pilot.REPO / "tasks" / "ts-tz-utc" / "task.json").read_text(encoding="utf-8")
    )["prompt"]
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "plan_id": "pilot-sequence-plan",
                "evaluation_manifest_id": "pilot-sequence-manifest",
                "evaluation_manifest_digest": manifest.digest,
                "baseline_arm": "bare",
                "arms": ["bare"],
                "chains": [
                    {
                        "chain_id": "c1",
                        "seed": 0,
                        "sessions": [
                            {
                                "task_id": "ts-json-sorted",
                                "position": 0,
                                "role": "source",
                                "user_input": source_prompt,
                            },
                            {
                                "task_id": "ts-tz-utc",
                                "position": 1,
                                "role": "target",
                                "user_input": target_prompt,
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pilot, "assert_preregistered", lambda _repo: None)
    validated: list[str] = []
    monkeypatch.setattr(
        pilot,
        "validate_plan",
        lambda plan, **_kwargs: validated.append(plan.plan_id),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pilot",
            "--arms",
            "bare",
            "--sequence-plan",
            str(plan_path),
            "--heldout-manifest",
            str(manifest_path),
            "--dry-run",
        ],
    )
    assert asyncio.run(pilot.main()) == 0
    output = capsys.readouterr().out
    assert validated == ["pilot-sequence-plan"]
    assert "sequence plan pilot-sequence-plan" in output
    assert "would run 2 session(s)" in output
