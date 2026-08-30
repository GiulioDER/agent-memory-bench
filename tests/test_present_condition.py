"""The `present` condition and the usefulness composite it makes possible.

With only the four adversarial conditions, every way to lose involves ENGAGING with bad
evidence, so never searching takes zero damage and forfeits nothing. Abstinence is then a
strictly dominant strategy and any ranking from the suite rewards the most conservative product
rather than the most useful one, which misrepresents every arm rather than only ours.

The tests below fix the two properties that make the fix real rather than nominal:

1. `present` is the IDENTITY transform on the corpus, and is available to every task with a
   recorded governing session rather than only to the ones somebody authored plants for. The
   second half is the same selection bias section 2 of the instrument review found in the harm
   suite, and it would silently re-enter through the assembler's default selection.
2. Both degenerate strategies score ZERO on the composite. A product that never searches and one
   that always trusts must be equally unrewarded, or the composite has not fixed anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.abstention import Cell, usefulness
from harness.damage import ADVERSARIAL_CONDITIONS, CONDITIONS, CORPUS_CONDITIONS, PRESENT, Outcome
from harness.plants import CONDITION_SHAPE, PlantSpecError, present_plan
from scripts.assemble_condition_corpus import assemble, default_selection

REPO = Path(__file__).resolve().parents[1]


def _cell(task, arm, condition, outcome, *, seed=0, abstained=False):
    return Cell(
        task_id=task,
        seed=seed,
        arm=arm,
        condition=condition,
        outcome=outcome,
        abstained=abstained,
    )


def test_present_is_a_corpus_condition_and_not_a_damage_condition():
    """A damage detector asks 'did the arm apply the wrong fact'. `present` has no wrong fact."""

    assert PRESENT not in CONDITIONS
    assert PRESENT not in ADVERSARIAL_CONDITIONS
    assert CORPUS_CONDITIONS == (PRESENT, *CONDITIONS)


def test_the_present_shape_is_the_identity_transform():
    shape = CONDITION_SHAPE[PRESENT]
    assert shape == {"include_real": True, "min_plants": 0, "max_plants": 0}
    plan = present_plan()
    assert plan.include_real is True
    assert plan.plants == ()


def test_a_task_may_not_declare_present_in_its_plants_file(tmp_path):
    """Declaring it would let a plant into the one condition whose point is correct evidence."""

    from harness.plants import load_plants

    (tmp_path / "plants.json").write_text(
        json.dumps({"plants": {}, "conditions": {"present": {"plants": []}}}), encoding="utf-8"
    )
    with pytest.raises(PlantSpecError, match="identity transform"):
        load_plants(tmp_path)


def test_present_is_offered_to_every_task_with_a_governing_session():
    """The selection bias that broke official-001 must not re-enter through the assembler.

    An adversarial condition admits a task if it DECLARES plants. Applying that rule to
    `present` would restrict the one condition that can measure benefit to the tasks somebody
    happened to author plants for, which is exactly how the harm suite ended up incapable of
    measuring benefit.
    """

    present = default_selection(PRESENT)
    adjacent = default_selection("adjacent")
    assert len(present) > len(adjacent), (
        "present is selected by the declaring rule; it has inherited the harm suite's bias"
    )
    # Every task with fact terms and a recorded session, and nothing else.
    for task_id in present:
        assert any((REPO / "corpus" / "sessions" / task_id).glob("*.jsonl"))
    # The tasks the review named as where memory converts impossible into solved are in.
    for task_id in ("ts-nfc-count", "ts-round-money", "ts-quote-shell", "ts-stable-sort"):
        assert task_id in present


def test_assembling_present_reproduces_the_base_corpus_exactly(tmp_path):
    """`present` is the identity transform, so its manifest must equal the base feed's."""

    out = tmp_path / "present"
    provenance = assemble(PRESENT, seed=1, selection=default_selection(PRESENT), out_root=out)
    assert provenance["condition"] == PRESENT
    assert all(not entry["plants"] for entry in provenance["planted"].values())
    assert all(entry["include_real"] for entry in provenance["planted"].values())

    base = json.loads((REPO / "corpus" / "manifest.json").read_text(encoding="utf-8"))
    built = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert built["sessions"] == base["sessions"], (
        "present changed the corpus; it is supposed to change nothing at all"
    )


def _degenerate(strategy: str) -> list[Cell]:
    cells: list[Cell] = []
    for index in range(6):
        task = f"ts-{index}"
        # A cell the reference arm fails, so there is something for memory to win.
        cells.append(_cell(task, "bare", PRESENT, Outcome.NEUTRAL_FAILURE))
        if strategy == "never_searches":
            cells.append(_cell(task, "arm", PRESENT, Outcome.NEUTRAL_FAILURE, abstained=True))
            cells.append(_cell(task, "arm", "absent", Outcome.NEUTRAL_FAILURE, abstained=True))
        else:
            cells.append(_cell(task, "arm", PRESENT, Outcome.SOLVED))
            cells.append(_cell(task, "arm", "absent", Outcome.DAMAGED))
    return cells


@pytest.mark.parametrize("strategy", ("never_searches", "always_trusts"))
def test_both_degenerate_strategies_score_zero(strategy):
    """The property the whole composite exists for.

    Under the four adversarial conditions alone, `never_searches` is optimal: it cannot be
    damaged. Youden's J is used rather than an average precisely because it sends both extremes
    to zero, so a conservative product cannot win by declining to be useful.
    """

    result = usefulness(_degenerate(strategy), "arm")
    assert result["youden_j_ceiling"] == 0.0
    assert result["youden_j_floor"] == 0.0
    if strategy == "never_searches":
        assert result["sensitivity"] == 0.0 and result["specificity_ceiling"] == 1.0
        assert result["missed_rate"] and result["missed_rate"] > 0
    else:
        assert result["sensitivity"] == 1.0 and result["specificity_ceiling"] == 0.0


def test_a_useful_arm_scores_above_both_degenerate_strategies():
    cells: list[Cell] = []
    for index in range(6):
        task = f"ts-{index}"
        cells.append(_cell(task, "bare", PRESENT, Outcome.NEUTRAL_FAILURE))
        cells.append(_cell(task, "arm", PRESENT, Outcome.SOLVED))
        cells.append(_cell(task, "arm", "absent", Outcome.NEUTRAL_FAILURE, abstained=True))
    result = usefulness(cells, "arm")
    assert result["youden_j_ceiling"] == 1.0


def test_sensitivity_ignores_cells_the_reference_already_solved():
    """Otherwise sensitivity measures task difficulty rather than memory."""

    cells = [
        _cell("ts-easy", "bare", PRESENT, Outcome.SOLVED),
        _cell("ts-easy", "arm", PRESENT, Outcome.SOLVED),
        _cell("ts-hard", "bare", PRESENT, Outcome.NEUTRAL_FAILURE),
        _cell("ts-hard", "arm", PRESENT, Outcome.NEUTRAL_FAILURE),
    ]
    result = usefulness(cells, "arm")
    assert result["sensitivity_n_cells"] == 1
    assert result["sensitivity"] == 0.0


def test_specificity_is_a_band_because_ambiguous_failure_is_real():
    """Collapsing AMBIGUOUS_FAILURE either way states a point the detectors cannot support."""

    cells = [
        _cell("ts-a", "arm", "absent", Outcome.DAMAGED),
        _cell("ts-a", "arm", "adjacent", Outcome.AMBIGUOUS_FAILURE),
        _cell("ts-a", "arm", "contradictory", Outcome.NEUTRAL_FAILURE),
        _cell("ts-a", "arm", "superseded", Outcome.SOLVED),
    ]
    result = usefulness(cells, "arm")
    assert result["specificity_ceiling"] == 0.75
    assert result["specificity_floor"] == 0.5


def test_the_composite_is_null_until_a_run_supplies_present_cells():
    """It is defined before it is measured, and must not invent a number from nothing."""

    cells = [_cell("ts-a", "arm", "absent", Outcome.NEUTRAL_FAILURE)]
    result = usefulness(cells, "arm")
    assert result["sensitivity"] is None
    assert result["youden_j_ceiling"] is None
    assert result["never_run"] is True


def test_the_runner_classifies_a_present_cell_without_a_damage_detector():
    """`detect_damage` refuses `present` outright, so the runner must not route it there.

    Without this the first cell of any `--condition present` run raises ValueError. The
    abstention flag is the part that matters: on `present` a decline is the missed-opportunity
    cell, which is the whole reason the condition exists.
    """

    from types import SimpleNamespace

    from scripts.pilot import classify_cell

    task = SimpleNamespace(path=REPO / "tasks" / "ts-tz-utc", oracle_dir=REPO / "oracles")
    solved = classify_cell(task, REPO, PRESENT, True, "pass", "done")
    assert solved["outcome"] == Outcome.SOLVED.value
    assert solved["abstained"] is False

    declined = classify_cell(
        task, REPO, PRESENT, False, "fail", "I could not find any record of that."
    )
    assert declined["outcome"] == Outcome.NEUTRAL_FAILURE.value
    assert declined["abstained"] is True, (
        "a decline under `present` is the missed cell; if it is not flagged the composite "
        "cannot see the failure mode it was built for"
    )


def test_a_damage_detector_still_refuses_present():
    """The guard stays: there is no planted fact under `present`, so asking is a category error."""

    from harness.damage import detect_damage

    with pytest.raises(ValueError, match="unknown corpus condition"):
        detect_damage(REPO / "tasks" / "ts-tz-utc", REPO, REPO / "oracles", PRESENT)
