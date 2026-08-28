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


def test_the_rate_is_cells_that_searched_over_cells_run(tmp_path):
    run = _run_dir(
        tmp_path,
        [_row("recall", 1, 0), _row("recall", 0, 1), _row("recall", 3, 2), _row("recall", 0, 3)],
    )
    assert search_rate_for(run)["recall"] == 0.5


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
