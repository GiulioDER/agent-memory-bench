from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.frozen_manifest import FrozenEvaluationManifest
from harness.sequence_plan import load_plan
from harness.sequence_preflight import validate_sequence_evaluation
from harness.sequence_validation import sequence_input_files


def _plan(digest: str):
    return load_plan(
        {
            "schema": 1,
            "plan_id": "plan-1",
            "evaluation_manifest_id": "manifest-1",
            "evaluation_manifest_digest": digest,
            "baseline_arm": "bare",
            "arms": ["bare", "recall"],
            "chains": [
                {
                    "chain_id": "c1",
                    "seed": 0,
                    "sessions": [
                        {
                            "task_id": "source",
                            "position": 0,
                            "role": "source",
                            "user_input": "learn",
                        },
                        {
                            "task_id": "target",
                            "position": 1,
                            "role": "target",
                            "user_input": "apply",
                        },
                    ],
                }
            ],
        }
    )


def _real_plan(digest: str):
    repo = Path(__file__).resolve().parents[1]

    def prompt(task_id: str) -> str:
        return json.loads((repo / "tasks" / task_id / "task.json").read_text())["prompt"]

    return load_plan(
        {
            "schema": 1,
            "plan_id": "coverage-plan",
            "evaluation_manifest_id": "coverage-manifest",
            "evaluation_manifest_digest": digest,
            "baseline_arm": "bare",
            "arms": ["bare", "recall"],
            "chains": [
                {
                    "chain_id": "c1",
                    "seed": 0,
                    "sessions": [
                        {
                            "task_id": "ts-atomic-write",
                            "position": 0,
                            "role": "source",
                            "user_input": prompt("ts-atomic-write"),
                        },
                        {
                            "task_id": "ts-bool-env",
                            "position": 1,
                            "role": "target",
                            "user_input": prompt("ts-bool-env"),
                        },
                    ],
                }
            ],
        }
    )


def test_preflight_verifies_bound_manifest(tmp_path):
    (tmp_path / "corpus.jsonl").write_text("corpus\n", encoding="utf-8")
    (tmp_path / "protocol.md").write_text("protocol\n", encoding="utf-8")
    manifest = FrozenEvaluationManifest.build(
        tmp_path,
        manifest_id="manifest-1",
        created_at="2026-09-17T12:00:00+00:00",
        corpus_files=["corpus.jsonl"],
        protocol_files=["protocol.md"],
    )
    result = validate_sequence_evaluation(
        _plan(manifest.digest),
        manifest,
    )
    assert result.to_dict() == {
        "plan_id": "plan-1",
        "plan_digest": _plan(manifest.digest).digest,
        "manifest_id": "manifest-1",
        "manifest_digest": manifest.digest,
        "chains": 1,
        "chain_lengths": [2],
        "corpus_files": ["corpus.jsonl"],
        "protocol_files": ["protocol.md"],
        "bound_sequence_files": [],
        "verified": True,
    }


def test_preflight_refuses_manifest_digest_mismatch(tmp_path):
    (tmp_path / "corpus.jsonl").write_text("corpus\n", encoding="utf-8")
    (tmp_path / "protocol.md").write_text("protocol\n", encoding="utf-8")
    manifest = FrozenEvaluationManifest.build(
        tmp_path,
        manifest_id="manifest-1",
        created_at="2026-09-17T12:00:00+00:00",
        corpus_files=["corpus.jsonl"],
        protocol_files=["protocol.md"],
    )
    with pytest.raises(ValueError, match="different digests"):
        validate_sequence_evaluation(_plan("a" * 64), manifest)


def test_preflight_requires_manifest_coverage_for_runtime_sequence_inputs():
    repo = Path(__file__).resolve().parents[1]
    initial = _real_plan("a" * 64)
    required = sequence_input_files(initial, repo_root=repo, tasks_root=repo / "tasks")
    manifest = FrozenEvaluationManifest.build(
        repo,
        manifest_id="coverage-manifest",
        created_at="2026-09-17T12:00:00+00:00",
        corpus_files=["corpus/manifest.json"],
        protocol_files=list(required),
    )
    result = validate_sequence_evaluation(
        _real_plan(manifest.digest),
        manifest,
        repo_root=repo,
        tasks_root=repo / "tasks",
    )
    assert result.bound_sequence_files == required


def test_preflight_rejects_manifest_missing_runtime_sequence_inputs():
    repo = Path(__file__).resolve().parents[1]
    manifest = FrozenEvaluationManifest.build(
        repo,
        manifest_id="coverage-manifest",
        created_at="2026-09-17T12:00:00+00:00",
        corpus_files=["corpus/manifest.json"],
        protocol_files=["preregistration/006-longitudinal-suite.md"],
    )
    with pytest.raises(ValueError, match="does not bind all sequence evaluation inputs"):
        validate_sequence_evaluation(
            _real_plan(manifest.digest),
            manifest,
            repo_root=repo,
            tasks_root=repo / "tasks",
        )
