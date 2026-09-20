from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.analyze_code_task_solve import ALL_TASKS, ARMS, analyze


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _write_run(root: Path, outcomes: dict[tuple[str, int, str], bool]) -> Path:
    run = root / "code4-task-solve-001"
    run.mkdir()
    artifact = _sha("artifact")
    records = []
    for (task, seed, arm), success in outcomes.items():
        model = "voyage-code-3" if arm == "code3_replay" else "voyage-code-4"
        records.append(
            {
                "task_id": task,
                "seed": seed,
                "arm": arm,
                "success": success,
                "input_tokens": 100,
                "output_tokens": 10,
                "model_turns": 2,
                "wall_time_ms": 1000,
                "metadata": {
                    "prompt_sha256": _sha(f"prompt {task} {arm}"),
                    "memory_diagnostic": {
                        "kind": arm,
                        "task_id": task,
                        "model": model,
                        "artifact_sha256": artifact,
                        "query_sha256": _sha(f"query {task}"),
                        "window_indices": list(range(10)),
                        "source_paths": [f"sessions/{index}.json" for index in range(10)],
                        "injected_text_sha256": _sha(f"evidence {task} {arm}"),
                        "injected_input_tokens": 50,
                        "status": "ok",
                    },
                },
            }
        )
    (run / "records.final.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    cells = {(task, seed) for task, seed, _arm in outcomes}
    (run / "admission.json").write_text(
        json.dumps(
            {
                "required_arms": list(ARMS),
                "admitted_cells": len(cells),
                "discarded_cells": [],
            }
        ),
        encoding="utf-8",
    )
    (run / "environment.json").write_text(
        json.dumps({"code_retrieval_artifact_sha256": artifact}), encoding="utf-8"
    )
    (run / "costs.json").write_text(json.dumps({"arms": {}}), encoding="utf-8")
    return run


def test_analyzer_applies_frozen_advancement_rule(tmp_path: Path) -> None:
    outcomes = {}
    tasks = sorted(ALL_TASKS)
    for task in tasks:
        for seed in range(3):
            outcomes[(task, seed, "code3_replay")] = True
            outcomes[(task, seed, "code4_replay")] = True
    for task in tasks[:3]:
        outcomes[(task, 0, "code3_replay")] = False
    result = analyze(_write_run(tmp_path, outcomes))
    assert result["admitted_cells"] == 102
    assert result["overall"]["net_wins"] == 3
    assert result["advance_to_official_cambench"] is True


def test_analyzer_refuses_artifact_identity_drift(tmp_path: Path) -> None:
    task = min(ALL_TASKS)
    outcomes = {
        (task, 0, "code3_replay"): False,
        (task, 0, "code4_replay"): True,
    }
    run = _write_run(tmp_path, outcomes)
    rows = [json.loads(line) for line in (run / "records.final.jsonl").read_text().splitlines()]
    rows[0]["metadata"]["memory_diagnostic"]["artifact_sha256"] = _sha("wrong")
    (run / "records.final.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        analyze(run, require_full_roster=False)


def test_analyzer_refuses_replay_drift_across_seeds(tmp_path: Path) -> None:
    task = min(ALL_TASKS)
    outcomes = {
        (task, seed, arm): True for seed in range(2) for arm in ARMS
    }
    run = _write_run(tmp_path, outcomes)
    rows = [json.loads(line) for line in (run / "records.final.jsonl").read_text().splitlines()]
    rows[-1]["metadata"]["memory_diagnostic"]["window_indices"] = list(range(1, 11))
    (run / "records.final.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="replay identity changed"):
        analyze(run, require_full_roster=False)


def test_analyzer_reconstructs_diagnostic_omitted_by_public_receipt(tmp_path: Path) -> None:
    task = min(ALL_TASKS)
    outcomes = {
        (task, 0, "code3_replay"): False,
        (task, 0, "code4_replay"): True,
    }
    run = _write_run(tmp_path, outcomes)
    rows = [json.loads(line) for line in (run / "records.final.jsonl").read_text().splitlines()]
    prompt_hashes = {arm: {task: None} for arm in ARMS}
    for row in rows:
        row["metadata"].pop("memory_diagnostic")
        prompt_hashes[row["arm"]][task] = row["metadata"]["prompt_sha256"]
    (run / "records.final.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    artifact_path = Path(__file__).parents[1] / "results/retrieval/091-code4-task-solve-evidence.json"
    environment = {
        "code_retrieval_artifact_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        "prompt_sha256_by_task": prompt_hashes,
    }
    (run / "environment.json").write_text(json.dumps(environment), encoding="utf-8")

    result = analyze(run, require_full_roster=False)

    assert result["overall"]["net_wins"] == 1
    assert result["evidence_by_task"][task]["code4_replay"]["window_indices"]
