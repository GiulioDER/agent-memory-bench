"""The recall arm must receive the same instruction the pilots froze, not a terser substitute.

scripts/pilot.py has always taken --recall-instruction, and pilot-003 and pilot-004 both ran it as
`skill`: the 5,817 byte adapters/recall/skill.md, which teaches searching by operation and symptom
rather than by task vocabulary. scripts/diagnostic.py never carried the flag over and silently used
the 615 byte one-liner from config.frozen.json instead.

That is not a cosmetic difference. Measured on diagnostic-009, same corpus and same wiring: the
recall arm searched in 16% of sessions, against 85.7% in pilot-004. A diagnostic built to explain
pilot-004's failure taxonomy was therefore measuring a different treatment from pilot-004.

The anchor test below pins the skill to the sha256 pilot-004 recorded in its own environment.json,
so a future edit to skill.md cannot silently make the diagnostic incomparable to the run it exists
to explain without a test going red and saying why.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from adapters.recall.adapter import RecallAdapter
from scripts.pilot import recall_instruction

REPO = Path(__file__).resolve().parents[1]

#: pilot-004-placebo/environment.json recorded recall_instruction_sha256 with this prefix while
#: running recall_instruction == "skill". It is the provenance link between the two runs.
PILOT_004_SKILL_SHA_PREFIX = "1fdc9e85a556c2cc"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_the_skill_still_matches_the_one_pilot_004_ran():
    """Mutation: editing skill.md. Legitimate, but it makes new runs incomparable to pilot-004,
    and that must be a deliberate act rather than a silent one."""

    assert _sha(recall_instruction("skill")).startswith(PILOT_004_SKILL_SHA_PREFIX)


def test_pilot_004_really_did_record_that_hash():
    """Read the claim from the artifact rather than trusting the constant above."""

    env = REPO / "results" / "pilot-004-placebo" / "environment.json"
    if not env.is_file():
        pytest.skip("pilot-004 results not present in this checkout")
    recorded = json.loads(env.read_text(encoding="utf-8"))
    assert recorded["recall_instruction"] == "skill"
    assert recorded["recall_instruction_sha256"].startswith(PILOT_004_SKILL_SHA_PREFIX)


def test_the_two_variants_are_genuinely_different():
    one = recall_instruction("oneliner")
    skill = recall_instruction("skill")
    assert one != skill
    assert len(skill) > 10 * len(one), "the skill should be substantially more than a one-liner"
    assert skill.startswith("# Check memory before acting")


def test_the_adapter_uses_the_override_when_given(tmp_path, monkeypatch, recall_location):
    """Mutation: ignoring the override. The diagnostic silently reverts to the one-liner and its
    recall arm stops being the treatment pilot-004 measured."""

    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    bundle = tmp_path / "static.md"
    bundle.write_text("# notes\n\nthe governing detail\n", encoding="utf-8")
    adapter = RecallAdapter(tmp_path / "adapter", bundle, instruction=recall_instruction("skill"))
    spec = adapter.build_for_task(tmp_path / "session", "ns", "ts-alpha", "do the thing")
    text = Path(spec.append_system_prompt_file).read_text(encoding="utf-8")
    assert text.startswith("# Check memory before acting")
    assert "the governing detail" in text, "the static bundle must still follow the instruction"


def test_without_an_override_the_frozen_one_liner_is_used(tmp_path, monkeypatch, recall_location):
    """scripts/smoke.py and any other existing caller must keep the frozen behaviour."""

    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    bundle = tmp_path / "static.md"
    bundle.write_text("# notes\n\nthe governing detail\n", encoding="utf-8")
    adapter = RecallAdapter(tmp_path / "adapter", bundle)
    spec = adapter.build_for_task(tmp_path / "session", "ns", "ts-alpha", "do the thing")
    text = Path(spec.append_system_prompt_file).read_text(encoding="utf-8")
    assert text.startswith("You have a persistent project memory")


def test_the_instruction_leads_the_prompt_in_both_variants(tmp_path, monkeypatch, recall_location):
    """Buried after the bundle, the instruction measured a 0% search rate, and then the benchmark
    is measuring prompt placement rather than retrieval."""

    monkeypatch.setenv("RECALL_DSN", "postgresql://irrelevant/for-this-test")
    bundle = tmp_path / "static.md"
    bundle.write_text("# notes\n\nSENTINEL\n", encoding="utf-8")
    for variant in ("oneliner", "skill"):
        adapter = RecallAdapter(
            tmp_path / f"adapter-{variant}", bundle, instruction=recall_instruction(variant)
        )
        spec = adapter.build_for_task(
            tmp_path / f"session-{variant}", "ns", "ts-alpha", "do the thing"
        )
        text = Path(spec.append_system_prompt_file).read_text(encoding="utf-8")
        assert text.index("SENTINEL") > 100, f"{variant}: bundle came before the instruction"
