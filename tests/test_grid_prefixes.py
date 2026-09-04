"""A task class that exists on disk must be either in the grid or excluded on the record.

`scripts/pilot.py` selected tasks with a bare `startswith("ts-")` until 2026-08-30. That single
string is why the library stayed monotonic in practice: the three `xs-*` cross-session synthesis
tasks were authored, pass their own tests, and had never once appeared in a grid. No one decided
that. A string comparison decided it, silently, and it would have swallowed any new class the same
way.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.tasks import discover_tasks
from scripts.pilot import EXCLUDED_PREFIXES, GRID_PREFIXES, SELECTABLE_PREFIXES


def _prefixes() -> set[str]:
    return {task.task_id.split("-")[0] + "-" for task in discover_tasks()}


def test_every_class_on_disk_is_accounted_for():
    """Mutation: author a new task class and do not register it.

    Without this, the class is invisible to every run while looking complete on disk: fixtures,
    checker, references, corpus and all. That is exactly what happened to `xs-*`.
    """

    known = set(SELECTABLE_PREFIXES) | set(EXCLUDED_PREFIXES)
    unaccounted = sorted(p for p in _prefixes() if p not in known)
    assert not unaccounted, (
        f"task class(es) {unaccounted} exist on disk but are neither in GRID_PREFIXES nor listed "
        f"in EXCLUDED_PREFIXES, so every run skips them without saying so"
    )


def test_an_exclusion_carries_a_reason():
    """An absence with no reason attached becomes an oversight the next time anyone looks."""

    for prefix, reason in EXCLUDED_PREFIXES.items():
        assert reason and len(reason) > 20, f"{prefix} is excluded with no stated reason"


def test_the_failed_approach_class_is_runnable_but_not_yet_in_the_default_grid():
    """Mutation: drop `fa-` from SELECTABLE_PREFIXES, or slip it into GRID_PREFIXES.

    Both directions are wrong and for opposite reasons. Unselectable means the class cannot be
    calibrated at all, which is how `xs-` spent its whole life. In the DEFAULT grid means an
    ordinary run silently measures something the preregistered runs did not contain.

    Selectable-but-not-default is the state a new class should sit in until a preregistration
    admits it.
    """

    assert "fa-" in SELECTABLE_PREFIXES, "a class nobody can select cannot be calibrated"
    assert "fa-" not in GRID_PREFIXES, "admitting a class to the default grid needs a record"
    assert any(t.task_id.startswith("fa-") for t in discover_tasks())


def test_the_grid_and_the_exclusions_do_not_overlap():
    assert not (set(SELECTABLE_PREFIXES) & set(EXCLUDED_PREFIXES))
