"""The integration contract is a promise to people outside this project, so it is tested.

`docs/INTEGRATION-CONTRACT.md` tells a competing product's maintainer what their arm may ship and
what it must prove. A document that drifts from the code is worse than no document, because the
reader has no way to tell: they would build against a field that no longer exists and discover it
when their run is discarded.

The tripwire at the bottom is the interesting one. The contract states that hook integration is
supported and UNTESTED, and that honesty expires the moment an adapter ships hooks. That test
fails when it does, which forces the sentence to be rewritten rather than left standing as a
stale caveat that undersells the harness.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from harness.adapters.base import ArmSpec
from harness.claude_exec import ClaudeExecConfig
from harness.gate import AdmissionSignal

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "docs" / "INTEGRATION-CONTRACT.md"
TEXT = CONTRACT.read_text(encoding="utf-8")


def _fields(cls) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


def test_every_armspec_field_the_contract_names_actually_exists():
    """Parsed out of the document, not checked as a substring.

    An earlier version asserted `field in TEXT` for a fixed list, which passes even when the doc
    renames a field, because the old name still appears elsewhere on the page. A mutation proved
    it: `ArmSpec.config_dir` became `ArmSpec.plugin_dir` in the offer table and the test stayed
    green. This reads what the document actually promises.
    """

    promised = set(re.findall(r"`ArmSpec\.([a-z_]+)`", TEXT))
    assert promised, "the contract names no ArmSpec field; the offer table has gone"
    unreal = sorted(promised - _fields(ArmSpec))
    assert not unreal, f"the contract offers ArmSpec fields that do not exist: {unreal}"


@pytest.mark.parametrize(
    "field", ["mcp_config", "append_system_prompt_file", "config_dir", "env"]
)
def test_the_surfaces_a_competitor_needs_are_offered(field):
    assert field in _fields(ArmSpec)
    assert f"`ArmSpec.{field}`" in TEXT, f"ArmSpec.{field} exists but is not offered in the table"


@pytest.mark.parametrize("field", ["mcp_tool_prefixes", "required_hooks", "sandbox_paths"])
def test_the_proofs_the_contract_demands_exist_on_the_gate(field):
    assert field in _fields(AdmissionSignal)
    assert field in TEXT


def test_hook_integration_is_actually_wired_through_the_executor():
    """The contract tells a hook-based product to use config_dir. If the executor cannot take
    one, that instruction sends them into a wall."""

    assert "config_dir" in _fields(ClaudeExecConfig)


def test_the_full_pilot_passes_each_arm_config_dir_to_the_executor():
    source = (REPO / "scripts" / "pilot.py").read_text(encoding="utf-8")
    assert "config_dir=spec.config_dir" in source


def test_the_contract_does_not_promise_an_instruction_length_cap():
    """A cap would be an arbitrary line advantaging whoever sits under it. recall's skill is 5,428
    characters; the contract's answer to a longer one is to ship it."""

    assert "no length cap" in TEXT.lower()
    skill = REPO / "adapters" / "recall" / "skill.md"
    if skill.is_file():
        assert "5,428" in TEXT, "the stated size of recall's own instruction should be current"


def test_not_calling_memory_is_a_result_rather_than_a_discard():
    """This is the clause that protects a competitor from being scored zero for a wiring failure,
    and equally from being excused for a discoverability failure. Both halves must be stated."""

    assert "RESULT, not a discard" in TEXT
    assert "discoverability" in TEXT


# ---------------------------------------------------------------------------------------
# the tripwire
# ---------------------------------------------------------------------------------------


def test_the_untested_hook_claim_expires_when_an_adapter_ships_hooks():
    """Keep the contract honest while the first hook adapter awaits its smoke test.

    Once the smoke test succeeds, the status must be promoted to exercised and this tripwire must
    be updated with the measured run artifact.
    """

    shipping = [
        path.parent.name
        for path in sorted((REPO / "adapters").glob("*/adapter.py"))
        if "config_dir=" in path.read_text(encoding="utf-8")
    ]
    assert shipping == ["supermemory"], (
        f"unexpected hook adapters: {shipping}; update this tripwire with the shipped set"
    )
    assert "pending smoke verification" in TEXT
