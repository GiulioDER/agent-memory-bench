"""The failed-approach class must admit more than one correct answer, or it is not that class.

`fa-dedup-key` is the exemplar. Its corpus records an OUTCOME, that deduplicating on `order_id`
lost 1,214 real orders because two suppliers reuse an id range, and it explicitly declines to
choose a replacement key. So the memory supplies an EXCLUSION, and the agent picks freely from
what survives it.

That only works if the checker grades properties rather than comparing against one expected
artefact. Every other checker in this suite does the latter, which admits exactly one solution.
These tests are what stops this one drifting back to that.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

TASK = REPO / "tasks" / "fa-dedup-key"
ORACLE = REPO / "oracles" / "fa-dedup-key"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(reference: str) -> tuple[bool, str]:
    checker = _load(TASK / "checker.py", "fa_checker")
    with tempfile.TemporaryDirectory() as temp:
        workdir = Path(temp) / "w"
        shutil.copytree(TASK / "tree", workdir)
        _load(TASK / "reference" / f"{reference}.py", f"fa_{reference}").apply(workdir)
        return checker.check(workdir, ORACLE)


@pytest.mark.parametrize("reference", ["informed", "alternative"])
def test_more_than_one_key_is_accepted(reference):
    """Mutation: make the checker compare against a single expected output.

    `informed` keys on (supplier, order_id). `alternative` keys on the full order identity. The
    corpus excludes keying on order_id alone and says nothing about what to use instead, so both
    satisfy it and both must pass. If only one does, the task has become "recall the one right
    answer", which is the shape the other thirty tasks already have.
    """

    ok, why = _run(reference)
    assert ok, f"{reference} is a correct solution and must pass: {why}"


def test_the_excluded_approach_still_fails():
    """The other half. A checker that admits everything admits the failed approach too."""

    ok, why = _run("naive")
    assert not ok
    assert "dropped" in why, why


def test_the_trap_that_pushes_an_agent_towards_the_failed_approach_is_real():
    """Deduplicating on the WHOLE record must also fail, and for the opposite reason.

    This is what makes the task hard rather than merely arbitrary. Whole-record comparison is the
    other obvious option, and a redelivered order differs in `received_at`, so every duplicate
    survives. An agent that tries it locally watches it fail and is pushed towards keying on
    `order_id`, which is exactly the approach the corpus records as having lost records.

    If this ever starts passing, the trap is gone: the safe-looking option would work, nobody
    would reach for the id, and the memory would have nothing to prevent.
    """

    ok, why = _run("whole_record")
    assert not ok
    assert "survived" in why, why


def test_the_memory_states_an_outcome_and_never_the_fix():
    """Mutation: add a fact term that names the replacement key.

    The class is defined by what the corpus withholds. A fact term saying "key on supplier and
    order_id" would turn this back into a stated convention, and the task would test the same
    thing the other thirty test.
    """

    import json

    terms = json.loads((TASK / "task.json").read_text(encoding="utf-8"))["fact_terms"]
    assert terms, "the task must declare fact terms"
    prescriptive = [t for t in terms if "supplier" in t.lower() and "order_id" in t.lower()]
    assert not prescriptive, (
        f"fact terms must describe the OUTCOME, not the fix; these name a key: {prescriptive}"
    )
