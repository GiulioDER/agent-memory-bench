"""Tests for private corpus leakage detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.challenge_pack import load_private_pack
from harness.challenge_pack_audit import ChallengePackLeakageError, audit_pack_corpus


def _pack(root: Path):
    files = {
        "corpus/session.txt": "memory only",
        "fixtures/task-a/input.txt": "fixture",
        "prompts/task-a.txt": "prompt",
        "checkers/task-a/checker.py": "checker",
        "oracles/task-a/value.txt": "secret oracle",
        "references/task-a/answer.txt": "reference",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (root / "pack.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "amb-private-evaluation-pack",
                "visibility": "private",
                "pack_id": "pack-a",
                "source_public_commit": "commit-a",
                "scoring_version": "score-a",
                "corpus": "corpus",
                "tasks": [
                    {
                        "task_id": "task-a",
                        "fixture": "fixtures/task-a",
                        "prompt": "prompts/task-a.txt",
                        "checker": "checkers/task-a/checker.py",
                        "oracle": "oracles/task-a",
                        "reference": "references/task-a",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return load_private_pack(root)


def test_corpus_audit_passes_without_exact_sensitive_overlap(tmp_path: Path):
    report = audit_pack_corpus(_pack(tmp_path / "pack"))
    assert report.exact_duplicates == ()
    assert report.corpus_files == 1


def test_corpus_audit_rejects_exact_oracle_overlap(tmp_path: Path):
    pack = _pack(tmp_path / "pack")
    (pack.root / "corpus/session.txt").write_text("secret oracle", encoding="utf-8")
    with pytest.raises(ChallengePackLeakageError, match="exactly duplicates"):
        audit_pack_corpus(load_private_pack(pack.root))
