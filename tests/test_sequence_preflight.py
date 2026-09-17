from __future__ import annotations

import pytest

from harness.frozen_manifest import FrozenEvaluationManifest
from harness.sequence_plan import load_plan
from harness.sequence_preflight import validate_sequence_evaluation


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
        "manifest_id": "manifest-1",
        "manifest_digest": manifest.digest,
        "chains": 1,
        "chain_lengths": [2],
        "corpus_files": ["corpus.jsonl"],
        "protocol_files": ["protocol.md"],
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
