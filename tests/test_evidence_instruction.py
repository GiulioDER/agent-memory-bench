"""The `evidence` variant must differ from `protocol` in ONE sentence and in nothing else.

Preregistration 025 asks whether a gate that WITHHOLDS beats a gate that ANNOTATES: `recall_search`
returns hits carrying a trust verdict, `recall_evidence` returns only the passages the trust layer
cleared and an empty bundle when it abstains. That contrast is interpretable only if the two arms
are otherwise byte-identical, because `001-skill-instruction` already established that instruction
strength alone moves search rate a long way (46/46 against 25/47).

`instructions.assert_shared_protocol` covers the protocol half. It CANNOT see the search sentence,
because that sentence is exactly what it substitutes out before comparing, so the one difference the
experiment turns on is the one difference the existing guard is blind to. Hence this file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness import instructions
from scripts.pilot import (
    PROTOCOL_FAMILY,
    RECALL_EVIDENCE_SENTENCE,
    RECALL_SEARCH_SENTENCE,
    instruction_arms_matched,
    memory_instructions,
    recall_instruction,
)

REPO = Path(__file__).resolve().parents[1]


def test_evidence_differs_from_protocol_only_in_the_search_sentence():
    """Mutation: add a clause to RECALL_EVIDENCE_SENTENCE, or edit the protocol under one variant.

    Substituting each variant's own sentence back out must leave the SAME remainder. If it does not,
    the arms differ somewhere beyond the tool name and the run measures prompt engineering.
    """

    protocol = recall_instruction("protocol")
    evidence = recall_instruction("evidence")
    assert protocol != evidence

    assert RECALL_SEARCH_SENTENCE in protocol
    assert RECALL_EVIDENCE_SENTENCE in evidence
    assert protocol.replace(RECALL_SEARCH_SENTENCE, "") == evidence.replace(
        RECALL_EVIDENCE_SENTENCE, ""
    )


def test_the_evidence_sentence_names_the_enforcing_tool_and_not_the_advisory_one():
    """Mutation: point the sentence back at recall_search. The whole treatment would vanish while
    every other assertion in this file still passed, because the shapes are identical."""

    assert "recall_evidence" in RECALL_EVIDENCE_SENTENCE
    assert "recall_search" not in RECALL_EVIDENCE_SENTENCE
    assert "recall_search" in RECALL_SEARCH_SENTENCE
    assert "recall_evidence" not in RECALL_SEARCH_SENTENCE


def test_the_evidence_sentence_says_what_an_empty_bundle_means():
    """The registered wording. An empty bundle is the mechanism under test, and an agent that is
    not told what it means will read zero passages as a failed search and answer anyway."""

    assert "empty bundle" in RECALL_EVIDENCE_SENTENCE
    assert "do not know" in RECALL_EVIDENCE_SENTENCE


def test_the_search_sentence_stays_one_sentence_by_the_protocol_s_own_rule():
    """`portable_protocol` refuses a slot containing a blank line, because a section there would be
    uncapped per-arm text outside the appendix budget. Assert the variant obeys it."""

    assert "\n\n" not in RECALL_EVIDENCE_SENTENCE
    instructions.portable_protocol(RECALL_EVIDENCE_SENTENCE)


def test_evidence_is_in_the_protocol_family_so_the_other_arms_are_matched():
    """Mutation: drop `evidence` from PROTOCOL_FAMILY.

    That single deletion would leave the recall arm on the shared protocol while fs_grep silently
    reverted to its historical unmatched sentence AND `assert_shared_protocol` stopped running, so
    the run would be asymmetric with every gate green. Three behaviours key on this tuple.
    """

    assert "evidence" in PROTOCOL_FAMILY

    arms = ("bare", "recall", "fs_grep")
    for variant in PROTOCOL_FAMILY:
        texts = memory_instructions(variant, arms)
        instructions.assert_shared_protocol(texts)
        assert texts["bare"] == ""

    protocol_texts = memory_instructions("protocol", arms)
    evidence_texts = memory_instructions("evidence", arms)
    assert protocol_texts["fs_grep"] == evidence_texts["fs_grep"]
    assert protocol_texts["recall"] != evidence_texts["recall"]


def test_an_unknown_variant_is_still_refused():
    """The dispatch is a chain of `if`s, so a new branch is exactly where a fallthrough gets lost."""

    with pytest.raises(ValueError, match="unknown recall instruction variant"):
        recall_instruction("enforcement")


def test_the_frozen_variants_are_untouched_by_the_new_one():
    """`skill` is the sha256-pinned provenance anchor for pilot-002 through pilot-004, and this
    change must not have moved it or `oneliner`. Cheap, and it is the reason `evidence` is built on
    `protocol` rather than on `skill` at all."""

    assert "recall_search" in recall_instruction("oneliner")
    assert recall_instruction("skill") not in (
        recall_instruction("protocol"),
        recall_instruction("evidence"),
    )


def test_the_published_fairness_flag_agrees_with_the_check_actually_run():
    """The predicate itself: true for the whole family, false for the unmatched variants.

    ⚠️ Measured, not assumed: this test does NOT catch the bug it was written for. Restoring
    `args.memory_instruction == "protocol"` at the environment.json site leaves this green, because
    it exercises the predicate and the bug is at the CALL SITE. The next test is the one that goes
    red, and the pair is kept because a behavioural check that silently covers nothing is how a
    guard comes to be believed without ever having been watched fail.
    """

    for variant in PROTOCOL_FAMILY:
        assert instruction_arms_matched(variant) is True
        # the same predicate must be the one gating the assertion
        instructions.assert_shared_protocol(memory_instructions(variant, ("bare", "recall", "fs_grep")))

    for variant in ("skill", "oneliner"):
        assert instruction_arms_matched(variant) is False


def test_the_environment_artifact_uses_the_predicate_and_not_a_literal():
    """Mutation: restore `args.memory_instruction == "protocol"` at the environment.json site.

    That literal was a FOURTH site keying on the variant name, missed when PROTOCOL_FAMILY replaced
    the other three, and missed again by a grep whose own exclude pattern contained the word `arms`.
    Under `evidence` the enforcement ran while the artifact published
    `instruction_arms_matched: false`, so the run would have disclosed that its arms were unmatched
    immediately after the code asserted they were.

    This reads the SOURCE rather than the behaviour, deliberately: nothing downstream consumes the
    flag, so no behavioural assertion can reach the call site. Verified red under the mutation.
    """

    source = (REPO / "scripts" / "pilot.py").read_text(encoding="utf-8")
    assert '"instruction_arms_matched": instruction_arms_matched(' in source
    assert '"instruction_arms_matched": args.memory_instruction ==' not in source
