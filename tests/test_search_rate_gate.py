"""The search rate decides whether the abstention endpoints mean anything.

An arm that never called its memory cannot be damaged by evidence it never retrieved. So a low
search rate does not weaken the damage rate, it VOIDS it, and a zero damage rate on an arm that
never searched would read as "this product is safe" when it means "this product was not used".

The floor is 0.50, taken from preregistration 002's eligibility rule rather than invented here, so
the benchmark uses one number for one idea.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.abstention import MEMORY_ARMS, SEARCH_RATE_FLOOR, search_rate_for

REPO = Path(__file__).resolve().parents[1]


def _run_dir(tmp_path: Path, rows: list[dict]) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    (run / "records.final.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    return run


def _row(arm: str, calls: int, seed: int = 0) -> dict:
    return {"task_id": "ts-tz-utc", "seed": seed, "arm": arm, "memory_call_count": calls}


def test_the_floor_comes_from_the_eligibility_rule():
    """Mutation: inventing a different number here. Two thresholds for one idea is how a run
    passes one gate and fails the other with nobody noticing which was meant."""

    assert SEARCH_RATE_FLOOR == 0.50
    text = (REPO / "preregistration" / "002-model-freeze.md").read_text(encoding="utf-8")
    assert "reached-given-searched is at least" in text
    assert "`0.50`" in text


def test_an_arm_that_never_searched_reports_zero_rather_than_vanishing(tmp_path):
    """THE assertion. Mutation: dropping arms with no searches from the result. The reader would
    see no search-rate line at all for the arm whose endpoints are void, which is precisely the
    case this exists to surface."""

    run = _run_dir(tmp_path, [_row("recall", 0, s) for s in range(3)])
    rates = search_rate_for(run)
    assert rates == {"recall": 0.0}
    assert rates["recall"] < SEARCH_RATE_FLOOR


def test_arms_with_no_memory_surface_have_no_search_rate(tmp_path):
    """`bare` and `claude_md` cannot search, so reporting 0.0 for them would read as a failure
    rather than as an absence, and would trip the floor warning on every run."""

    run = _run_dir(tmp_path, [_row("bare", 0), _row("claude_md", 0), _row("recall", 1)])
    assert set(search_rate_for(run)) == {"recall"}
    assert "bare" not in MEMORY_ARMS and "claude_md" not in MEMORY_ARMS


def test_the_rate_is_cells_that_searched_over_cells_admitted(tmp_path):
    """⚠️ Renamed 2026-08-30. This was `..._over_cells_run`, and that name was half of a
    three-way disagreement about what the number means.

    `search_rate_for`'s docstring said ADMITTED cells, its body counted every record, this test
    asserted cells RUN by name, and `main()` gated admitted-cell endpoints on the result. With no
    discards the two denominators coincide, which is why this fixture never distinguished them
    and the disagreement survived.

    Both are computed now. The default is admitted, because that is the population the endpoints
    the floor gates are computed over.
    """

    run = _run_dir(
        tmp_path,
        [_row("recall", 1, 0), _row("recall", 0, 1), _row("recall", 3, 2), _row("recall", 0, 3)],
    )
    assert search_rate_for(run)["recall"] == 0.5
    assert search_rate_for(run, admitted_only=False)["recall"] == 0.5, (
        "with no discards the two denominators must agree; a fixture where they cannot differ "
        "is what let three artefacts disagree for months"
    )


def test_the_two_denominators_differ_exactly_by_the_discards(tmp_path):
    """RED before the fix: the admitted rate was not computed at all, so it could not differ.

    Four cells, of which the two that never searched are discarded. Admitted: 2 of 2. Run: 2 of
    4. A discarded cell is discarded for wiring or error reasons, so the direction of the gap is
    data-dependent, not conservative: on `diagnostic-010` the discarded cells searched MORE often
    than the admitted ones and the all-cells rate is the higher of the two.
    """

    import json

    run = _run_dir(
        tmp_path,
        [_row("recall", 1, 0), _row("recall", 1, 1), _row("recall", 0, 2), _row("recall", 0, 3)],
    )
    rows = [json.loads(line) for line in (run / "records.final.jsonl").read_text().splitlines()]
    never_searched = [
        [r["task_id"], r["seed"]] for r in rows if not r.get("memory_call_count")
    ]
    (run / "admission.json").write_text(
        json.dumps({"discarded_cells": never_searched}), encoding="utf-8"
    )

    assert search_rate_for(run)["recall"] == 1.0, "every ADMITTED cell searched"
    assert search_rate_for(run, admitted_only=False)["recall"] == 0.5, (
        "half of every cell RUN searched; this is the number that answers whether the model "
        "reached for its memory at all"
    )


def test_both_rates_are_published_under_distinct_names():
    """A reader must be able to see the gap rather than take one denominator on trust."""

    import inspect

    from scripts import abstention

    source = inspect.getsource(abstention.main)
    assert 'report["search_rates"] = search_rates' in source
    assert 'report["search_rates_all_cells"]' in source, (
        "only one denominator is published, so a reader cannot see which one the floor used"
    )
    assert "interpretability(search_rates)" in source, (
        "the floor must be applied to the ADMITTED rate, since the endpoints it gates are "
        "computed over admitted cells"
    )


def test_a_missing_run_directory_is_empty_rather_than_an_error(tmp_path):
    assert search_rate_for(tmp_path / "nope") == {}


def test_the_published_pilots_clear_the_floor():
    """Guards the premise. If the runs this floor was calibrated against did not clear it, the
    floor is wrong rather than the new run being anomalous."""

    for run_id in ("pilot-003-deepseek", "pilot-004-placebo"):
        run = REPO / "results" / run_id
        if not (run / "records.final.jsonl").is_file():
            continue
        rate = search_rate_for(run).get("recall")
        assert rate is not None and rate >= SEARCH_RATE_FLOOR, (
            f"{run_id} recall search rate {rate} is below the floor this benchmark applies to new "
            f"runs; the floor cannot be stricter than the runs it was drawn from"
        )


# ---------------------------------------------------------------------------------------------
# AMB-034, found by an adversarial verifier during the 2026-08-30 audit and by no auditor.
#
# `search_rate_for` keys its result off the arms it OBSERVES in the records, so a memory arm that
# produced none never appears. The floor is then applied to a dict it is not in, and
# `any(rate < FLOOR for rate in search_rates.values())` is False because nothing is left to be
# below it. The gate passed BECAUSE the evidence was missing.
#
# This is the same defect class as the endpoints tautology in scripts/verify_run.py, and it is the
# exact silence `_classify_arms` was added to end: "a reader sees a table with one fewer row
# rather than a warning". That guard validates arm NAMES, so it could not catch this.
# ---------------------------------------------------------------------------------------------


def test_a_memory_arm_with_no_records_is_not_interpretable():
    """RED before the fix: the arm was absent from `interpretable`, so nothing said it was unknown."""

    from scripts.abstention import fill_missing_search_rates, interpretability

    filled = fill_missing_search_rates(
        {"recall[absent]": 0.9}, ["bare", "recall", "mempalace"], ["absent"]
    )
    assert filled["mempalace[absent]"] is None, "the absent arm was not filled in"
    assert "bare[absent]" not in filled, "only MEMORY arms carry a search rate"

    interpretable = interpretability(filled)
    assert interpretable["mempalace[absent]"] is False, (
        "an arm that produced no records is LESS interpretable than one with a low rate, not more"
    )
    assert interpretable["recall[absent]"] is True


def test_the_floor_fires_when_a_rate_is_missing_entirely():
    """RED before the fix: `any()` over the surviving rates could not see the absent arm."""

    from scripts.abstention import below_the_floor

    assert below_the_floor({"recall[absent]": 0.9, "mempalace[absent]": None}), (
        "a missing rate must trip the floor; it is a stronger signal than a low one"
    )


def test_the_gate_fills_every_requested_memory_arm():
    """The source-level guarantee: the fill covers memory arms x completed conditions."""

    import inspect

    from scripts import abstention

    source = inspect.getsource(abstention.main)
    assert "fill_missing_search_rates(" in source, (
        "main() does not fill missing memory arms, so an arm with no records vanishes silently"
    )
    assert "below_the_floor(" in source, "main() does not use the floor check that sees a None"

    # and the honest case must still pass, or the guard above is satisfied by refusing everything
    assert abstention.below_the_floor({"recall[absent]": 0.9}) is False


def test_every_arm_that_has_ever_run_is_classified():
    """RED before 2026-08-30: an eight-arm grid that had already run was refused.

    `_classify_arms` refuses an arm in neither set, and it is right to: `mempalace` was missing
    from MEMORY_ARMS for the whole of official-001, so that run published endpoints for an arm
    whose search rate nobody knew. But `oracle_memory` and `recall_prefetch` were in neither set
    while both had run, so the guard blocked a grid the harness had already executed. The guard
    was correct and the registry was incomplete, which is the same shape as the omission it was
    written to prevent, one arm class further out.
    """

    from scripts.abstention import MEMORY_ARMS, NON_MEMORY_ARMS, _classify_arms

    every_arm_with_an_adapter = [
        "bare", "claude_md", "placebo", "recall",
        "mempalace", "fs_grep", "cachly", "oracle_memory", "recall_prefetch",
    ]
    unclassified = [
        a for a in every_arm_with_an_adapter if a not in (MEMORY_ARMS | NON_MEMORY_ARMS)
    ]
    assert not unclassified, (
        f"{unclassified} have adapters and have produced records, but are in neither set, so a "
        f"grid naming them is refused before the first cell"
    )
    _classify_arms(every_arm_with_an_adapter)


def test_a_control_that_retrieves_outside_the_agent_is_not_a_memory_arm():
    """Membership is decided by whether THE AGENT has a retrieval surface, not by whether the
    arm retrieves at all.

    `oracle_memory` supplies verified evidence "without memory tools"; `recall_prefetch` runs the
    same published recall search from the HARNESS side and describes itself as
    `"memory": "harness prefetch"`. In both the agent is handed evidence and has no memory tool
    to call, so `memory_call_count` is 0 in every cell by construction.

    Classifying them as memory arms would put them permanently below the 0.50 floor and void
    their endpoints in every run, destroying the one thing a ceiling control is for: telling
    "every arm scored alike" apart from "the tasks allow nothing better".
    """

    from scripts.abstention import MEMORY_ARMS, NON_MEMORY_ARMS

    for arm in ("oracle_memory", "recall_prefetch"):
        assert arm in NON_MEMORY_ARMS, f"{arm} would be voided by the search-rate floor"
        assert arm not in MEMORY_ARMS
    for arm in ("recall", "mempalace", "fs_grep", "cachly"):
        assert arm in MEMORY_ARMS, f"{arm} retrieves through the agent and needs a search rate"
