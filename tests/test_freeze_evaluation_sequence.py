from __future__ import annotations

import json
import sys
from pathlib import Path

from harness.frozen_manifest import FrozenEvaluationManifest
from scripts.freeze_evaluation import main


def _write_task(root: Path, task_id: str, prompt: str, *, fact_terms: list[str]) -> None:
    task = root / "tasks" / task_id
    (task / "tree").mkdir(parents=True)
    (root / "oracles" / task_id).mkdir(parents=True)
    (task / "task.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "kind": "primary",
                "prompt": prompt,
                "fact_terms": fact_terms,
            }
        ),
        encoding="utf-8",
    )
    (task / "checker.py").write_text("# checker\n", encoding="utf-8")
    (task / "tree" / "README.md").write_text("fixture\n", encoding="utf-8")
    (root / "oracles" / task_id / "driver.py").write_text("# oracle\n", encoding="utf-8")


def test_sequence_plan_freeze_binds_plan_tasks_and_oracles(tmp_path, monkeypatch):
    _write_task(tmp_path, "source", "learn the rule", fact_terms=["secret rule"])
    _write_task(tmp_path, "target", "apply the rule", fact_terms=[])
    (tmp_path / "corpus.txt").write_text("corpus\n", encoding="utf-8")
    (tmp_path / "protocol.md").write_text("protocol\n", encoding="utf-8")
    (tmp_path / "plan.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "plan_id": "freeze-test",
                "evaluation_manifest_id": "freeze-manifest",
                "evaluation_manifest_digest": "0" * 64,
                "baseline_arm": "bare",
                "arms": ["bare"],
                "chains": [
                    {
                        "chain_id": "c1",
                        "seed": 0,
                        "sessions": [
                            {
                                "task_id": "source",
                                "position": 0,
                                "role": "source",
                                "user_input": "learn the rule",
                            },
                            {
                                "task_id": "target",
                                "position": 1,
                                "role": "target",
                                "user_input": "apply the rule",
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "heldout.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freeze_evaluation",
            "--repo-root",
            str(tmp_path),
            "--output",
            str(output),
            "--manifest-id",
            "freeze-manifest",
            "--created-at",
            "2026-09-17T12:00:00+00:00",
            "--corpus-file",
            "corpus.txt",
            "--protocol-file",
            "protocol.md",
            "--sequence-plan",
            "plan.json",
        ],
    )

    assert main() == 0
    manifest = FrozenEvaluationManifest.load(output, root=tmp_path)
    protocol_files = set(manifest.data["protocol_files"])
    assert "plan.json" not in protocol_files
    assert {
        "protocol.md",
        "tasks/source/task.json",
        "tasks/source/checker.py",
        "tasks/source/tree/README.md",
        "oracles/source/driver.py",
        "tasks/target/task.json",
        "tasks/target/checker.py",
        "tasks/target/tree/README.md",
        "oracles/target/driver.py",
    } <= protocol_files
