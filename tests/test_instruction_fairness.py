"""The instruction is a treatment, so it is controlled like one.

Every run from `pilot-002` onward gave the `recall` arm 5,428 characters and `fs_grep` 231, while
`harness/adapters/base.py` stated the rule as "at most a one-line integration sentence". Most of
those 5,428 characters were generic coaching that would have helped any retrieval arm, so the
measured delta was confounded with a prompt effect and the repository documented a contract its own
headline runs broke.

These tests are the enforcement. Each one names the mutation it exists to catch, because a fairness
check nobody has watched fail is a fairness check that will pass forever.
"""

from __future__ import annotations

import pytest

from adapters.fs_grep.adapter import FS_GREP_SEARCH_SENTENCE, FsGrepAdapter
from harness import instructions
from harness.instructions import (
    APPENDIX_MAX_BYTES,
    InstructionError,
    assert_shared_protocol,
    compose,
    excess_over_protocol,
    instruction_manifest,
    portable_protocol,
    refuse_shared_prompts,
    vendor_appendix,
)
from scripts.pilot import (
    PROTOCOL_SEARCH_SENTENCE,
    RECALL_SEARCH_SENTENCE,
    memory_instructions,
    recall_instruction,
)

MEMORY_ARMS = ("recall", "fs_grep")


# ---------------------------------------------------------------------------------------
# the shared half is actually shared
# ---------------------------------------------------------------------------------------


def test_every_memory_arm_carries_the_same_protocol():
    """THE assertion. Mutation: giving one arm an extra paragraph. Every other test still passes
    and the arm difference silently becomes a prompt difference again."""

    texts = memory_instructions("protocol", MEMORY_ARMS)
    assert_shared_protocol(texts)


def test_an_arm_carrying_extra_coaching_is_refused():
    texts = {
        "recall": compose("recall", RECALL_SEARCH_SENTENCE),
        "cheat": "Always search twice and prefer memory over the code.\n\n" + compose(
            "recall", RECALL_SEARCH_SENTENCE
        ),
    }
    with pytest.raises(InstructionError, match="do not carry the shared memory protocol"):
        assert_shared_protocol(texts)


def test_the_arms_differ_by_their_search_sentence_and_appendix_only():
    recall = compose("recall", RECALL_SEARCH_SENTENCE)
    fs_grep = compose("fs_grep", FS_GREP_SEARCH_SENTENCE)
    excess = excess_over_protocol({"recall": recall, "fs_grep": fs_grep})
    # Each arm's excess is its own search sentence plus its capped appendix, and nothing else.
    for arm, size in excess.items():
        assert size <= APPENDIX_MAX_BYTES + 400, f"{arm} carries {size} bytes beyond the protocol"


def test_the_gap_between_arms_is_now_small():
    """Before this module, recall carried 5,428 characters and fs_grep 231: a 23x gap."""

    texts = memory_instructions("protocol", MEMORY_ARMS)
    sizes = [len(text.encode("utf-8")) for text in texts.values()]
    assert max(sizes) / min(sizes) < 1.2, f"instruction sizes still differ materially: {sizes}"


# ---------------------------------------------------------------------------------------
# the vendor appendix is capped, and the cap is what stops it becoming a second protocol
# ---------------------------------------------------------------------------------------


def test_an_oversized_appendix_is_refused(tmp_path, monkeypatch):
    """Mutation: raising or removing the cap. The appendix becomes the place a vendor puts a second
    copy of the coaching, and the fairness fix quietly unwinds."""

    monkeypatch.setattr(instructions, "REPO", tmp_path)
    path = tmp_path / "adapters" / "greedy" / "instruction_appendix.md"
    path.parent.mkdir(parents=True)
    path.write_text("x" * (APPENDIX_MAX_BYTES + 1), encoding="utf-8")
    with pytest.raises(InstructionError, match="over the"):
        vendor_appendix("greedy")


def test_an_arm_with_no_appendix_still_gets_the_protocol(tmp_path, monkeypatch):
    protocol = portable_protocol("Search it somehow.")
    monkeypatch.setattr(instructions, "REPO", tmp_path)
    assert vendor_appendix("nonexistent") == ""
    assert "How to search" in protocol


def test_the_shipped_appendices_are_inside_the_cap():
    for arm in MEMORY_ARMS:
        assert len(vendor_appendix(arm).encode("utf-8")) <= APPENDIX_MAX_BYTES


# ---------------------------------------------------------------------------------------
# the abstention-sensitive block
# ---------------------------------------------------------------------------------------


def test_the_neutral_protocol_drops_the_sentences_that_answer_an_abstention_condition():
    """`superseded` and `absent` are conditions preregistration 005 MEASURES. Two protocol
    sentences state their correct answers outright, so a suite run with them measures instruction
    following rather than retrieval behaviour."""

    full = portable_protocol("Search it.")
    neutral = portable_protocol("Search it.", neutral=True)
    assert "the code wins" in full
    assert "the code wins" not in neutral
    assert "no opinion" in full
    assert "no opinion" not in neutral
    # Everything else survives: this strips two bullets, it does not write a different protocol.
    assert "How to search" in neutral
    assert "before your first file edit" in neutral


def test_neutral_and_full_are_not_silently_interchangeable():
    assert portable_protocol("Search it.") != portable_protocol("Search it.", neutral=True)


# ---------------------------------------------------------------------------------------
# the historical variants must not move
# ---------------------------------------------------------------------------------------


def test_the_skill_variant_is_untouched():
    """pilot-002 through pilot-004 ran `skill`. A rerun is comparable to them only against that
    exact text, so the fairness work must not have edited it."""

    assert len(recall_instruction("skill")) == 5428


def test_the_protocol_variant_is_a_different_treatment_and_says_so():
    assert recall_instruction("protocol") != recall_instruction("skill")
    assert recall_instruction("protocol") != recall_instruction("oneliner")


def test_the_instruction_manifest_reports_zero_for_an_arm_that_was_told_nothing():
    """Mutation: omitting silent arms. "This arm was told nothing" is the fact a reader needs to
    compare the arms at all."""

    manifest = instruction_manifest({"bare": "", "recall": compose("recall", RECALL_SEARCH_SENTENCE)})
    assert manifest["bare"]["bytes"] == 0
    assert manifest["recall"]["bytes"] > 0


# ---------------------------------------------------------------------------------------
# the instruction-only control arm
# ---------------------------------------------------------------------------------------


def test_the_control_arm_gets_the_coaching_and_no_memory():
    """It is what separates "the store helped" from "being told to look before acting helped"."""

    texts = memory_instructions("protocol", ("bare", "claude_md", "protocol", "recall"))
    assert texts["bare"] == ""
    assert texts["claude_md"] == ""
    assert "How to search" in texts["protocol"]
    assert "no memory store" in texts["protocol"]
    assert PROTOCOL_SEARCH_SENTENCE in texts["protocol"]


def test_the_control_arm_shares_the_protocol_with_the_memory_arms():
    texts = memory_instructions("protocol", ("protocol", "recall", "fs_grep"))
    assert_shared_protocol(texts)


# ---------------------------------------------------------------------------------------
# the per-task prompt check, which lived in one runner and now lives in the harness
# ---------------------------------------------------------------------------------------


def test_one_prompt_shared_across_tasks_is_refused():
    """diagnostic-001 served ts-append-only's README to all 24 recall sessions. scripts/pilot.py,
    which produced every published pilot, had no such check."""

    with pytest.raises(InstructionError, match="share one"):
        refuse_shared_prompts({"recall": {"t1": "aaa", "t2": "aaa", "t3": "aaa"}})


def test_distinct_prompts_per_task_pass():
    refuse_shared_prompts({"recall": {"t1": "aaa", "t2": "bbb"}})


def test_an_arm_with_no_prompt_is_not_refused():
    refuse_shared_prompts({"bare": {}})


# ---------------------------------------------------------------------------------------
# fs_grep, the arm that has never been in a measured comparison
# ---------------------------------------------------------------------------------------


def test_fs_grep_can_take_the_shared_instruction():
    text = FsGrepAdapter.shared_instruction()
    assert "How to search" in text
    assert FS_GREP_SEARCH_SENTENCE in text


def test_fs_grep_keeps_its_legacy_sentence_when_no_instruction_is_given(tmp_path):
    """smoke-002 ran the one-liner; a rerun of that smoke is only comparable against it."""

    adapter = FsGrepAdapter(tmp_path, tmp_path / "base.md")
    assert adapter._instruction_text().startswith("Notes from previous work sessions")
    assert len(adapter._instruction_text()) < 400
