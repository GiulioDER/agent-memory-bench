"""Gates that were green because they could not see, and the mutations that would blind them again.

Three defects closed on 2026-08-28, all the same shape: a literal-string check comparing BYTES
where a reader sees TEXT.

1. Markdown emphasis. `ts-dedup-order`'s planted session said "the *first* occurrence" and
   "first-occurrence deduplication", both of which state that task's governing fact, and both
   passed a substring test for `first occurrence`.
2. JSON escaping. Every corpus file is JSONL, so a phrase spanning a line break inside a recorded
   message sits in the bytes as an escaped newline, which no whitespace normalisation collapses.
3. Scope. `corpus/sessions/smoke/` is in the manifest and in every arm's feed, and the audit
   iterated discovered TASK ids, so it never opened those two files.

`scripts/audit_plants.py` was fixed for (1). `scripts/audit_corpus.py`, which guards the REAL
corpus rather than the plants, was not, and (2) and (3) were open in both.
"""

from __future__ import annotations

import json

from harness.plants import normalise
from scripts.audit_corpus import content_words, readable_text

# ---------------------------------------------------------------------------------------
# what the old test could not see
# ---------------------------------------------------------------------------------------


def test_markdown_emphasis_no_longer_hides_a_term():
    """The exact string that defeated the plant gate."""

    assert "first occurrence" not in "the *first* occurrence".lower()
    assert "first occurrence" in normalise("the *first* occurrence")


def test_hyphenation_no_longer_hides_a_term():
    assert "first occurrence" not in "first-occurrence deduplication".lower()
    assert "first occurrence" in normalise("first-occurrence deduplication")


def test_a_phrase_spanning_a_jsonl_line_break_is_visible(tmp_path):
    """Mutation: reading the file bytes instead of decoding it. The escaped newline hides the
    phrase and the audit reports clean."""

    path = tmp_path / "s.jsonl"
    path.write_text(
        json.dumps({"role": "user", "content": "ids use a restricted\nalphabet everywhere"}) + "\n",
        encoding="utf-8",
    )
    raw = normalise(path.read_text(encoding="utf-8"))
    assert "restricted alphabet" not in raw, "the escaped newline should hide it in the raw bytes"
    assert "restricted alphabet" in readable_text(path)


def test_tool_results_are_searched_too(tmp_path):
    """A governing fact quoted back by a tool is as readable as one the model typed."""

    path = tmp_path / "s.jsonl"
    path.write_text(
        json.dumps(
            {"role": "assistant", "tool_name": "Read", "tool_result": "timestamps are UTC"}
        )
        + "\n",
        encoding="utf-8",
    )
    assert "timestamps are utc" in readable_text(path)


def test_a_malformed_line_is_compared_raw_rather_than_skipped(tmp_path):
    """Mutation: `continue` on a JSONDecodeError. Skipping a line is how a leak hides."""

    path = tmp_path / "s.jsonl"
    path.write_text('{"role": "user"\nnot json at all: restricted alphabet\n', encoding="utf-8")
    assert "restricted alphabet" in readable_text(path)


def test_a_non_jsonl_file_is_read_whole(tmp_path):
    path = tmp_path / "README.md"
    path.write_text("# ordergen\n\nIds use a *restricted* alphabet.\n", encoding="utf-8")
    assert "restricted alphabet" in readable_text(path)


# ---------------------------------------------------------------------------------------
# the live corpus, which is the claim that matters
# ---------------------------------------------------------------------------------------


def test_the_real_corpus_passes_the_hardened_audit():
    """The audit is only worth having if it is run. Mutation: any future task whose fact term
    leaks into another task's sessions, a distractor, a fixture, a plant, or its own prompt."""

    from scripts.audit_corpus import main

    assert main() == 0


def test_the_audit_now_reads_the_smoke_sessions(tmp_path):
    """corpus/sessions/smoke/ is in every arm's feed and was invisible to the containment check.

    Not a fixture test: this asserts against the real tree, because the defect was that the real
    tree had a directory the glob never reached.
    """

    from pathlib import Path

    import scripts.audit_corpus as audit

    smoke = audit.REPO / "corpus" / "sessions" / "smoke"
    assert smoke.is_dir(), "the directory this test exists for is gone; delete the test too"
    reached = sorted((audit.REPO / "corpus" / "sessions").rglob("*.jsonl"))
    assert any(Path(p).parent.name == "smoke" for p in reached)


# ---------------------------------------------------------------------------------------
# correlated tasks, which the per-task bootstrap assumes away
# ---------------------------------------------------------------------------------------


def test_content_words_ignore_shared_english():
    """Mutation: dropping the stop list. Every pair of tasks then "overlaps" and the report is
    noise, which is the same as having no report."""

    assert content_words(("never a range", "the file is not on the list")) == {"range", "file",
                                                                              "list"}


def test_two_tasks_stating_one_convention_are_reported():
    a = content_words(("regenerated only via the script", "never hand-edit"))
    b = content_words(("maintained only via the script", "hand edits get lost"))
    shared = a & b
    assert {"script", "hand"} <= shared, (
        "ts-golden-regen and ts-ignore-gen encode one convention; the overlap report exists to "
        "surface exactly this pair"
    )
