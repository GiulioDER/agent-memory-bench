"""The normaliser that a plain substring test needed, and the checks that depend on it.

A recorded agent writes prose, and prose carries emphasis. `ts-dedup-order`'s planted session
contained "the *first* occurrence" and "first-occurrence deduplication", both of which state that
task's governing fact outright, and both passed `record_plant.py`'s gate: the asterisks and the
hyphen broke the literal match. The plant stated the very convention it existed to withhold, and
the whole condition would have answered its own question while every gate reported green.

That is the failure this module exists to prevent recurring, so the tests below are written
against the exact strings that slipped through.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.plants import normalise
from harness.tasks import discover_tasks

REPO = Path(__file__).resolve().parents[1]
PLANTS = REPO / "corpus" / "plants"


# ---------------------------------------------------------------------------------------
# the normaliser
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "keeping the *first* occurrence of each event id",
        "because of first-occurrence deduplication",
        "the **first** occurrence wins",
        "`first occurrence` semantics",
        "the _first_ occurrence",
        "first   occurrence",
    ],
    ids=["emphasis", "hyphen", "strong", "code", "underscore", "whitespace"],
)
def test_emphasis_and_joiners_cannot_hide_a_term(text):
    """Every one of these states the fact. A plain `in` test misses all but the last."""

    assert normalise("first occurrence") in normalise(text)


def test_the_naive_test_really_did_miss_these():
    """Guards the premise. If a plain substring test would have caught these, the normaliser is
    solving a problem that does not exist and this whole module is noise."""

    for text in ("the *first* occurrence", "first-occurrence deduplication"):
        assert "first occurrence" not in text.lower()


def test_normalise_collapses_whitespace_rather_than_removing_it():
    """Mutation: `_SPACE.sub("")` instead of `_SPACE.sub(" ")`.

    Word boundaries would vanish, so terms would start matching across unrelated adjacent words
    and every plant would be rejected for facts it does not state. Asserted on the boundary
    directly, because a leak example cannot tell the two behaviours apart: both reject the same
    strings, and only the surviving space distinguishes them.
    """

    assert normalise("a   b") == "a b"
    assert normalise("first\n\noccurrence") == "first occurrence"
    assert " " in normalise("first occurrence")


# ---------------------------------------------------------------------------------------
# the corpus as it stands
# ---------------------------------------------------------------------------------------


@pytest.mark.skipif(not PLANTS.is_dir(), reason="no plants recorded in this checkout")
def test_no_recorded_plant_states_its_task_s_governing_fact():
    """THE assertion. A plant that states the real convention makes its condition answer its own
    question, and the resulting damage rate would be measuring nothing.

    This re-checks the corpus rather than trusting `record_plant.py`, which admitted exactly such
    a plant before the normaliser existed.
    """

    tasks = {task.task_id: task for task in discover_tasks()}
    checked = 0
    for recording in sorted(PLANTS.rglob("*.jsonl")):
        task = tasks.get(recording.parent.name)
        if task is None:
            continue
        haystack = normalise(recording.read_text(encoding="utf-8"))
        leaked = [term for term in task.fact_terms if normalise(term) in haystack]
        assert not leaked, f"{recording.parent.name}/{recording.stem} states {leaked}"
        checked += 1
    assert checked, "no recorded plant was checked; the sweep matched nothing"


@pytest.mark.skipif(not PLANTS.is_dir(), reason="no plants recorded in this checkout")
def test_every_recorded_plant_carries_its_own_wrong_terms():
    """The other half of the inverted gate: a plant nothing can retrieve damages nothing, and
    would be scored as an ordinary miss rather than as an absent treatment."""

    for recording in sorted(PLANTS.rglob("*.jsonl")):
        spec_path = REPO / "tasks" / recording.parent.name / "plants.json"
        if not spec_path.is_file():
            continue
        declared = json.loads(spec_path.read_text(encoding="utf-8"))["plants"].get(recording.stem)
        assert declared, f"{recording} has no matching entry in plants.json"
        haystack = normalise(recording.read_text(encoding="utf-8"))
        missing = [t for t in declared["wrong_terms"] if normalise(t) not in haystack]
        assert not missing, f"{recording.parent.name}/{recording.stem} is missing {missing}"
