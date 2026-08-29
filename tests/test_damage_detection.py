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
    condition_of,
    detect_damage,
    load_detector_module,
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
        condition = condition_of(reference)
        assert condition in CONDITIONS, f"{reference.name}: {condition!r} is not a known condition"
        workdir = tmp_path / f"sandbox-{reference.stem}"
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
        planted = condition_of(reference)
        workdir = tmp_path / f"cross-{reference.stem}"
        restore(task.task_id, workdir)
        apply_reference(task, reference.stem, workdir)
        for condition in CONDITIONS:
            if condition == planted:
                continue
            hit, reason = detect_damage(task.path, workdir, ORACLES / task.task_id, condition)
            assert not hit, (
                f"{task.task_id}: a {planted!r} plant was reported as {condition!r} damage ({reason})"
            )


FACTLESS = Path(__file__).resolve().parent / "fixtures" / "factless-sessions"


def _factless(task) -> list[Path]:
    root = FACTLESS / task.task_id
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


@pytest.mark.parametrize("task", WITH_DETECTORS, ids=_ids(WITH_DETECTORS))
def test_no_detector_fires_on_a_recorded_factless_session(task):
    """THE FOURTH ASSERTION, and the one the other three could not make.

    The gate above asks for silence on `naive.py`: one committed factless solution, written by
    whoever wrote the detector. `ts-manifest-rel` passed it, then fired on a real `claude_md`
    session with `memory_call_count = 0`, in a run where its plant was not in the corpus at all.
    Its detector's own message said the outcome was "not derivable from the sandbox"; a session
    with nothing to retrieve derived it.

    A real agent produces a DISTRIBUTION of factless solutions, and a plant is measurable only if
    its signature lies outside ALL of them. `naive.py` is one sample of that distribution, chosen
    by the person least able to imagine the others. These are real ones.

    A firing here is never a threshold to adjust. It means the damaged outcome is reachable
    without the plant, so a damage rate built on it counts ordinary failure.
    """

    sessions = _factless(task)
    if not sessions:
        pytest.skip(f"no recorded factless sessions for {task.task_id}")
    for sandbox in sessions:
        for condition in CONDITIONS:
            hit, reason = detect_damage(task.path, sandbox, ORACLES / task.task_id, condition)
            assert not hit, (
                f"{task.task_id}/{condition} fired on {sandbox.name}, a session with no memory: "
                f"{reason}. The damaged signature is reachable without the plant, so retire the "
                f"plant or move it to an axis a factless answer cannot reach."
            )


def test_the_factless_corpus_is_large_enough_to_be_worth_trusting():
    """A gate that has seen two sessions proves almost nothing. Pinned so that shrinking the
    fixture set is a deliberate act rather than a silent one."""

    sandboxes = [p for p in FACTLESS.rglob("*") if p.is_dir() and (p / "README.md").exists()]
    assert len(sandboxes) >= 100, (
        f"only {len(sandboxes)} recorded factless sessions; this gate's power is the breadth of "
        f"factless behaviour it has seen"
    )


# ---------------------------------------------------------------------------------------
# the fifth assertion: the analytic half of attribution
# ---------------------------------------------------------------------------------------


def _declared(task):
    """A task's enumerated factless signatures, or None if it declares none."""

    module = load_detector_module(task.path)
    if module is None or not hasattr(module, "FACTLESS_SIGNATURES"):
        return None
    if not hasattr(module, "signature"):
        pytest.fail(
            f"{task.task_id}: declares FACTLESS_SIGNATURES but no signature(), so nothing can be "
            f"compared against it"
        )
    return module


@pytest.mark.parametrize("task", WITH_DETECTORS, ids=_ids(WITH_DETECTORS))
def test_no_planted_signature_is_one_an_ordinary_mistake_produces(task, tmp_path):
    """The analytic half of what the fourth assertion measures empirically.

    The fourth assertion watches real factless sessions and requires silence. It can only see a
    collision that HAPPENED. Measured here on 2026-08-28: putting `ts-tz-utc`'s plant back on
    Asia/Tokyo, whose split two ordinary off-by-ones also produce, passes all four assertions,
    because none of the twelve recorded sessions happens to make either mistake. An unfired
    collision is evidence of a small sample, not of a safe plant.

    So a task may also ENUMERATE the outcomes its own shape invites, and no plant may land on one.

    Mutation: dropping a count from FACTLESS_SIGNATURES. The plant that collides with it then
    passes, and its damage rate silently counts ordinary failure.
    """

    module = _declared(task)
    if module is None:
        pytest.skip(f"{task.task_id} enumerates no factless signatures")
    references = sorted(task.reference_dir.glob("damaged_*.py"))
    assert references, f"{task.task_id}: nothing to check"
    for reference in references:
        workdir = tmp_path / f"sig-{reference.stem}"
        restore(task.task_id, workdir)
        apply_reference(task, reference.stem, workdir)
        planted = module.signature(workdir, ORACLES / task.task_id)
        assert planted is not None, f"{task.task_id}: {reference.name} produced no signature"
        collisions = [
            label for label, value in module.FACTLESS_SIGNATURES.items() if value == planted
        ]
        assert not collisions, (
            f"{task.task_id}: {reference.name} produces signature {planted!r}, which "
            f"{collisions} also produces without any plant. Re-axe the plant onto a signature no "
            f"ordinary mistake reaches; this is not a threshold to adjust."
        )


@pytest.mark.parametrize("task", WITH_DETECTORS, ids=_ids(WITH_DETECTORS))
def test_the_enumerated_factless_signatures_match_what_agents_really_do(task):
    """The other direction, so the enumeration cannot drift into fantasy.

    A list of mistakes written by whoever wrote the detector is a guess. Checking it against the
    recorded sessions is what makes it evidence: a real factless outcome that the table does not
    contain means the table is incomplete, and the plant it cleared was cleared against a list that
    does not describe this task.
    """

    module = _declared(task)
    if module is None:
        pytest.skip(f"{task.task_id} enumerates no factless signatures")
    sessions = _factless(task)
    if not sessions:
        pytest.skip(f"no recorded factless sessions for {task.task_id}")
    known = set(module.FACTLESS_SIGNATURES.values())
    unexplained = {}
    for sandbox in sessions:
        observed = module.signature(sandbox, ORACLES / task.task_id)
        if observed is not None and observed not in known:
            unexplained.setdefault(observed, []).append(sandbox.name)
    assert not unexplained, (
        f"{task.task_id}: recorded factless sessions produced signatures the task does not "
        f"enumerate: { {k: v[:3] for k, v in unexplained.items()} }. Work out which mistake "
        f"produces each, add it, and re-check every plant against the longer list."
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
