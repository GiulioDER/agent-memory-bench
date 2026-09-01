"""The `draft` protocol variant: one variable, shared by every arm, and refused if hand-edited.

Preregistration 024 rests on the claim that `draft` differs from `protocol` in exactly one section.
A claim like that decays the first time somebody edits the generated file, and it decays silently,
so these tests re-derive it rather than trusting it. That is the same reasoning as
`assert_shared_protocol`: the old contract only stated the rule.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness import instructions
from scripts.build_draft_protocol import CLOSE, OPEN, render

STANDARD = REPO / "adapters" / "_shared" / "memory_protocol.md"
DRAFT = REPO / "adapters" / "_shared" / "memory_protocol_draft.md"


def _bytes(path: Path) -> str:
    return path.read_text(encoding="utf-8", newline="")


# --- the one-variable claim, re-derived rather than trusted ------------------------------------


def test_the_committed_draft_is_what_the_generator_produces():
    """THE guard. A hand-edited draft could differ from `protocol` anywhere, and preregistration
    024 would then be measuring an unknown number of changes while reporting one."""
    assert _bytes(DRAFT) == render(), (
        "memory_protocol_draft.md is not what scripts/build_draft_protocol.py generates. "
        "Regenerate it; do not hand-edit it."
    )


def test_only_the_how_to_search_section_differs():
    std, draft = _bytes(STANDARD), _bytes(DRAFT)
    head_end = std.find(OPEN)
    assert head_end > 0
    assert std[:head_end] == draft[: draft.find(OPEN)], "the text BEFORE the section differs"
    assert std[std.find(CLOSE) :] == draft[draft.find(CLOSE) :], "the text AFTER the section differs"


def test_the_two_protocols_are_close_in_size():
    """Prompt length must not be the variable. A large gap would confound the comparison."""
    std, draft = len(_bytes(STANDARD).encode()), len(_bytes(DRAFT).encode())
    assert abs(draft - std) < 400, f"standard {std} against draft {draft}: too far apart"


def test_the_draft_actually_says_to_search_with_the_draft():
    """A generated file that lost its point would still pass every structural check above.

    ⚠️ Checks the GENERATOR's output as well as the committed file, and the second half was added
    because a mutation survived without it. Mutating `DRAFT_SECTION` left this test green, since it
    only read the committed bytes; only `test_the_committed_draft_is_what_the_generator_produces`
    caught it, and then only indirectly, as a staleness error rather than as "the draft no longer
    says to use the draft". A guard should fail for the reason it exists.
    """
    for label, text in (("committed", _bytes(DRAFT).lower()), ("generated", render().lower())):
        assert "the text you are about to write" in text, f"the {label} draft lost its own point"
        assert "search with that text itself" in text, f"the {label} draft lost its instruction"
    std = _bytes(STANDARD).lower()
    assert "the text you are about to write" not in std, "the standard protocol already says it"


# --- the variant plumbing ----------------------------------------------------------------------


def test_the_variant_is_selectable_and_unknown_names_are_refused():
    assert instructions.protocol_path("draft") == DRAFT
    assert instructions.protocol_path("protocol") == STANDARD
    with pytest.raises(instructions.InstructionError, match="unknown protocol variant"):
        instructions.protocol_path("drafft")


def test_an_unknown_variant_never_falls_back_to_the_standard_protocol():
    """Falling back would run the standard protocol under a variant's name and report the null as
    a finding about the variant. That is the failure this module exists to prevent across arms."""
    with pytest.raises(instructions.InstructionError):
        instructions.protocol_template(variant="nope")


def test_compose_carries_the_draft_through_to_the_arm_text():
    text = instructions.compose("recall", "Search it with `x`.", variant="draft")
    assert "the text you are about to write" in text.lower()
    assert "Search it with `x`." in text


def test_the_fairness_assertion_uses_the_variant_it_was_composed_with():
    """Checking a draft roster against the standard template would report every arm an offender."""
    roster = {
        arm: instructions.compose(arm, f"Search {arm}.", variant="draft")
        for arm in ("recall", "fs_grep", "mempalace")
    }
    instructions.assert_shared_protocol(roster, variant="draft")
    with pytest.raises(instructions.InstructionError, match="do not carry the shared"):
        instructions.assert_shared_protocol(roster, variant="protocol")


def test_a_mixed_roster_is_refused_under_either_variant():
    """The whole point: one run, one protocol. An arm on the other variant must not pass."""
    roster = {
        "recall": instructions.compose("recall", "Search recall.", variant="draft"),
        "mempalace": instructions.compose("mempalace", "Search mempalace.", variant="protocol"),
    }
    with pytest.raises(instructions.InstructionError, match="mempalace"):
        instructions.assert_shared_protocol(roster, variant="draft")


def test_neutral_still_strips_the_abstention_block_in_the_draft():
    text = instructions.portable_protocol("Search it.", neutral=True, variant="draft")
    assert "abstention-sensitive" not in text
    assert "the code wins" not in text


# --- the runner contract -----------------------------------------------------------------------


def test_pilot_offers_draft_and_treats_it_as_a_shared_protocol_variant():
    from scripts import pilot

    assert "draft" in pilot.SHARED_PROTOCOL_VARIANTS
    assert "protocol" in pilot.SHARED_PROTOCOL_VARIANTS
    assert "skill" not in pilot.SHARED_PROTOCOL_VARIANTS
    assert "oneliner" not in pilot.SHARED_PROTOCOL_VARIANTS


def test_every_memory_arm_gets_the_draft_protocol_not_just_recall():
    """If one arm kept the standard protocol the run would compare two things at once, which is
    exactly the confound `harness/instructions.py` was written to remove."""
    from scripts import pilot

    texts = pilot.memory_instructions("draft", ("bare", "recall", "fs_grep", "mempalace"))
    assert texts["bare"] == ""
    for arm in ("recall", "fs_grep", "mempalace"):
        assert "the text you are about to write" in texts[arm].lower(), arm


def test_the_skill_variant_is_untouched_by_any_of_this():
    """`adapters/recall/skill.md` is the provenance anchor for pilot-002 through pilot-004."""
    from scripts import pilot

    text = pilot.recall_instruction("skill")
    assert "the text you are about to write" not in text.lower()


def test_the_generator_check_mode_passes_on_the_committed_file():
    result = subprocess.run(
        [sys.executable, "-m", "scripts.build_draft_protocol", "--check"],
        cwd=REPO, capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
