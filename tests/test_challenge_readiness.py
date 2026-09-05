"""Tests for the aggregate challenge readiness report."""

from __future__ import annotations

import json
from pathlib import Path

from harness.challenge_readiness import evaluate_readiness, readiness_result


def test_readiness_reports_missing_external_gates(tmp_path: Path):
    result = readiness_result(
        evaluate_readiness(
            tmp_path / "missing-pack",
            tmp_path / "missing-policy",
            tmp_path / "missing-rules",
        )
    )
    assert result["status"] == "blocked"
    assert {gate["name"] for gate in result["gates"]} == {
        "private_pack",
        "corpus_leakage",
        "evaluation_policy",
        "final_rules",
        "release_record",
        "baseline_ordering",
    }


def test_readiness_requires_both_baseline_manifests(tmp_path: Path):
    for name, score in (("baseline.json", 0.8), ("bad.json", 0.1)):
        (tmp_path / name).write_text(json.dumps({"score": score}), encoding="utf-8")
    result = evaluate_readiness(
        tmp_path / "missing-pack",
        tmp_path / "missing-policy",
        tmp_path / "missing-rules",
        baseline_path=tmp_path / "baseline.json",
    )
    gate = next(gate for gate in result if gate.name == "baseline_ordering")
    assert gate.passed is False
