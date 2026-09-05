"""Tests for final contest rule validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.challenge_rules import ChallengeRulesError, load_rules, rules_digest


def _rules(path: Path, **overrides) -> Path:
    data = json.loads(
        (Path(__file__).parents[1] / "preregistration" / "challenge_rules.json").read_text()
    )
    data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_draft_rules_load_but_cannot_finalize(tmp_path: Path):
    path = _rules(tmp_path / "rules.json")
    assert load_rules(path)["status"] == "draft"
    with pytest.raises(ChallengeRulesError, match="status='final'"):
        load_rules(path, require_final=True)


def test_final_rules_reject_placeholders(tmp_path: Path):
    path = _rules(tmp_path / "rules.json", status="final")
    with pytest.raises(ChallengeRulesError, match="placeholders"):
        load_rules(path, require_final=True)


def test_rules_digest_changes_with_rule_bytes(tmp_path: Path):
    first = load_rules(_rules(tmp_path / "first.json"))
    second = load_rules(_rules(tmp_path / "second.json", appeal_window_days=14))
    assert rules_digest(first) != rules_digest(second)
