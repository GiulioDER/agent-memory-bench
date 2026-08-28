"""The gate a damage detector must pass before any harm rate built on it is worth reading.

`tests/test_references.py` is the checker's gate: a do-nothing sandbox fails, `naive` fails,
`informed` passes. A damage detector needs its own, and the middle assertion is the one that
carries the whole metric:

    informed              -> must NOT fire   (a correct answer is not damaged)
    naive                 -> must NOT fire   (factless failure is NEUTRAL, not harm)
    damaged_<condition>   -> MUST fire       (the planted fact was applied)

Without the middle one, "damage" degenerates into "failed", the metric measures nothing beyond the
success rate already reported, and every published harm number is the failure rate wearing a
different name.

A detector nobody has watched fire has not been tested, and one nobody has watched STAY SILENT on a
merely-wrong answer is worse: it will report damage everywhere and look decisive doing it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.damage import (
    CONDITIONS,
    ContradictoryVerdicts,
    Outcome,
    classify,
    detect_damage,
    net_harm,
)
from harness.sandbox import ORACLES, restore
from harness.tasks import apply_reference, discover_tasks, run_checker

TASKS = {task.task_id: task for task in discover_tasks()}
WITH_DETECTORS = [t for t in TASKS.values() if (t.path / "damage.py").is_file()]


def _ids(tasks):
    return [t.task_id for t in tasks]


# ---------------------------------------------------------------------------------------
# the three-way gate, per task that has a detector
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("task", WITH_DETECTORS, ids=_ids(WITH_DETECTORS))
def test_the_correct_solution_is_never_damaged(task, tmp_path):
    workdir = tmp_path / "sandbox"
    restore(task.task_id, workdir)
    apply_reference(task, "informed", workdir)
    ok, verdict = run_checker(task, workdir)
    assert ok, f"{task.task_id}: informed reference no longer passes: {verdict}"
    for condition in CONDITIONS:
        hit, reason = detect_damage(task.path, workdir, ORACLES / task.task_id, condition)
        assert not hit, f"{task.task_id}/{condition}: fired on the CORRECT answer: {reason}"


@pytest.mark.parametrize("task", WITH_DETECTORS, ids=_ids(WITH_DETECTORS))
def test_a_factless_failure_is_neutral_not_damage(task, tmp_path):
    """THE assertion the metric rests on. Mutation: making detect() return True whenever the
    checker fails. Every other test here still passes, and the harm rate silently becomes the
    failure rate."""

    workdir = tmp_path / "sandbox"
    restore(task.task_id, workdir)
    apply_reference(task, "naive", workdir)
    ok, _ = run_checker(task, workdir)
    assert not ok, f"{task.task_id}: naive reference unexpectedly passes"
    for condition in CONDITIONS:
        hit, reason = detect_damage(task.path, workdir, ORACLES / task.task_id, condition)
        assert not hit, (
            f"{task.task_id}/{condition}: attributed a FACTLESS failure to retrieved evidence "
            f"({reason}). Damage would then be indistinguishable from ordinary failure."
        )


@pytest.mark.parametrize("task", WITH_DETECTORS, ids=_ids(WITH_DETECTORS))
def test_the_planted_fact_is_detected_when_applied(task, tmp_path):
    """Mutation: detect() returning False unconditionally. Damage becomes unmeasurable and the
    suite reports a reassuring zero."""

    references = sorted(task.reference_dir.glob("damaged_*.py"))
    assert references, f"{task.task_id}: has damage.py but no damaged_* reference to prove it fires"
    for reference in references:
        condition = reference.stem.removeprefix("damaged_")
        assert condition in CONDITIONS, f"{reference.name}: {condition!r} is not a known condition"
        workdir = tmp_path / f"sandbox-{condition}"
        restore(task.task_id, workdir)
        apply_reference(task, reference.stem, workdir)
        ok, _ = run_checker(task, workdir)
        assert not ok, f"{task.task_id}/{condition}: the damaged reference PASSES the checker"
        hit, reason = detect_damage(task.path, workdir, ORACLES / task.task_id, condition)
        assert hit, f"{task.task_id}/{condition}: did not fire on a known-damaged sandbox: {reason}"


@pytest.mark.parametrize("task", WITH_DETECTORS, ids=_ids(WITH_DETECTORS))
def test_a_damaged_sandbox_is_not_attributed_to_the_wrong_condition(task, tmp_path):
    """A detector must answer about the condition it was asked about, not fire on any damage it
    recognises. Otherwise per-condition damage rates are meaningless."""

    for reference in sorted(task.reference_dir.glob("damaged_*.py")):
        planted = reference.stem.removeprefix("damaged_")
        workdir = tmp_path / f"cross-{planted}"
        restore(task.task_id, workdir)
        apply_reference(task, reference.stem, workdir)
        for condition in CONDITIONS:
            if condition == planted:
                continue
            hit, reason = detect_damage(task.path, workdir, ORACLES / task.task_id, condition)
            assert not hit, (
                f"{task.task_id}: a {planted!r} plant was reported as {condition!r} damage ({reason})"
            )


# ---------------------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------------------


def test_the_three_outcomes():
    assert classify(True, False) is Outcome.SOLVED
    assert classify(False, False) is Outcome.NEUTRAL_FAILURE
    assert classify(False, True) is Outcome.DAMAGED


def test_a_contradiction_raises_rather_than_picking_a_side():
    """Mutation: returning SOLVED, or DAMAGED, when both fire. Either buries a broken predicate
    inside a published rate instead of stopping to look at it."""

    with pytest.raises(ContradictoryVerdicts, match="cannot be both correct"):
        classify(True, True)


def test_an_unknown_condition_is_refused():
    with pytest.raises(ValueError, match="unknown corpus condition"):
        detect_damage(Path("."), Path("."), Path("."), "made-up")


def test_a_task_without_a_detector_reports_that_rather_than_guessing():
    hit, reason = detect_damage(Path("."), Path("."), Path("."), "absent")
    assert hit is False and "no damage detector" in reason


# ---------------------------------------------------------------------------------------
# the primary endpoint
# ---------------------------------------------------------------------------------------


def test_net_harm_counts_both_directions():
    """(arm_ok, bare_ok): one cell broken by memory, one fixed by it, two untouched."""

    stats = net_harm([(False, True), (True, False), (True, True), (False, False)])
    assert stats["harmed"] == 1 and stats["helped"] == 1
    assert stats["net_harm"] == 0.0
    assert stats["n_paired_cells"] == 4


def test_net_harm_is_not_the_failure_rate():
    """Mutation: counting only `not arm_ok`. An arm that fails a cell bare ALSO fails has harmed
    nobody, and conflating the two makes every weak arm look destructive."""

    stats = net_harm([(False, False)] * 10)
    assert stats["harmed"] == 0 and stats["net_harm"] == 0.0


def test_net_harm_refuses_an_empty_denominator():
    with pytest.raises(ValueError, match="needs a denominator"):
        net_harm([])
