"""Tests that the held out manifest is content bound and cannot drift silently."""

from __future__ import annotations

import json

import pytest

from harness.frozen_manifest import FrozenEvaluationManifest


def test_frozen_manifest_verifies_and_detects_content_change(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    protocol = tmp_path / "protocol.md"
    corpus.write_text("signal\n", encoding="utf-8")
    protocol.write_text("frozen protocol\n", encoding="utf-8")
    manifest = FrozenEvaluationManifest.build(
        tmp_path,
        manifest_id="sequence-selectivity-001",
        created_at="2026-09-17T12:00:00Z",
        corpus_files=["corpus.jsonl"],
        protocol_files=["protocol.md"],
    )
    manifest.verify()
    path = tmp_path / "heldout.json"
    manifest.write(path)
    loaded = FrozenEvaluationManifest.load(path, root=tmp_path)
    loaded.verify()
    corpus.write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hashes to"):
        loaded.verify()


def test_manifest_digest_cannot_be_edited_without_refusal(tmp_path):
    source = tmp_path / "source.txt"
    protocol = tmp_path / "protocol.md"
    source.write_text("source\n", encoding="utf-8")
    protocol.write_text("protocol\n", encoding="utf-8")
    manifest = FrozenEvaluationManifest.build(
        tmp_path,
        manifest_id="heldout",
        created_at="2026-09-17T12:00:00Z",
        corpus_files=["source.txt"],
        protocol_files=["protocol.md"],
    )
    path = tmp_path / "heldout.json"
    manifest.write(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["manifest_id"] = "edited"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        FrozenEvaluationManifest.load(path, root=tmp_path).verify()
