"""The abstention runner: the orchestrator, and the classification hook inside pilot.py.

Two guards here are load-bearing and neither is obvious from reading the code:

* **`bare` is mandatory.** Damage is "failed a cell `bare` solved", so a run without it produces
  endpoints that are undefined rather than merely weaker. `diagnostic-003` onward dropped `bare`,
  which is how the suite lost the ability to express harm in the first place.
* **Classification happens in the runner, not the analysis.** A damage detector needs the finished
  working tree, and by the time anything reads `records.jsonl` the sandbox is gone. If pilot stops
  writing the outcome, the analysis cannot recover it at any price short of re-running the grid.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PILOT = (REPO / "scripts" / "pilot.py").read_text(encoding="utf-8")


def _run(args, env_overrides=None):
    env = dict(os.environ)
    for key, value in (env_overrides or {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-m", "scripts.abstention", *args],
        cwd=str(REPO), capture_output=True, text=True, timeout=300, env=env, check=False,
    )


def _preregistration_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "preregistration/", "benchmarks/"],
        cwd=str(REPO), capture_output=True, text=True, timeout=60, check=False,
    )
    return bool(result.stdout.strip())


needs_clean_preregistration = pytest.mark.skipif(
    _preregistration_dirty(),
    reason="preregistration/ is uncommitted, so pilot refuses before any check under test",
)


# ---------------------------------------------------------------------------------------
# the mandatory reference arm
# ---------------------------------------------------------------------------------------


def test_a_run_without_bare_is_refused():
    """Mutation: dropping the check. The suite would run, produce a damage rate against no
    reference, and report a number whose definition was never satisfied."""

    result = _run(["--arms", "claude_md,recall", "--dry-run"])
    assert result.returncode != 0
    assert "mandatory" in result.stdout + result.stderr


def test_an_unknown_condition_is_refused():
    result = _run(["--arms", "bare", "--conditions", "made-up", "--dry-run"])
    assert "unknown condition" in result.stdout + result.stderr


@needs_clean_preregistration
def test_each_arm_ships_its_own_instruction_by_default():
    """Mutation: defaulting to `protocol`. That equalises the instruction across arms, which
    preregistration 006 forbids in terms: every arm is wired through its own official integration
    and the benchmark must not prescribe the route. `protocol` is a CONTROL arm that isolates
    coaching from retrieval; using it as the default would measure a common denominator no product
    ships, and would quietly answer a question 006 already answered.
    """

    result = _run(
        ["--run-id", "unit-probe", "--conditions", "absent", "--arms", "bare,recall",
         "--seeds", "1", "--dry-run"],
        {"RECALL_DSN": None, "OPENROUTER_API_KEY": "placeholder"},
    )
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "instruction variant 'skill'" in out, (
        f"the suite must default to each arm's own instruction; it reported: "
        f"{[line for line in out.splitlines() if 'instruction variant' in line]}"
    )


# ---------------------------------------------------------------------------------------
# task selection is data, not a flag
# ---------------------------------------------------------------------------------------


def test_selection_comes_from_the_tasks_that_declare_the_condition():
    from scripts.abstention import selection_for

    superseded = set(selection_for("superseded"))
    absent = set(selection_for("absent"))
    assert superseded, "no task declares superseded"
    assert "ts-tz-utc" in superseded
    # ts-dedup-order's plant was retired; it must not reappear in a selection.
    assert "ts-dedup-order" not in superseded
    assert superseded <= absent, "every planted task also declares absent"


def test_an_unknown_condition_is_refused_before_anything_is_assembled():
    """The outer guard, and the only one a caller can still trip from the command line."""

    result = _run(["--arms", "bare", "--conditions", "wrong_scope", "--dry-run"])
    combined = result.stdout + result.stderr
    assert "unknown condition" in combined
    assert "wrong_scope" in combined


def test_a_condition_with_no_corpus_behind_it_is_refused(monkeypatch):
    """The inner guard, which is no longer reachable from outside and is still load-bearing.

    This test used to pass `contradictory` on the command line, on the standing fact that no task
    declared it. Its own message said that if that changed the refusal path would need a different
    test, and on 2026-08-28 `ts-tz-utc` declared it. Every one of the four conditions is now
    declared by something, and an unknown name is caught by the outer guard above, so no CLI
    invocation reaches this branch any more.

    That does not make it dead code: it fires the moment a condition is added to `CONDITIONS`
    before any task has a corpus for it, which is the exact window in which a run would otherwise
    assemble an empty selection and report a clean zero for a condition that was never measured.
    So it is exercised where it now lives, in process.

    Mutation: deleting the `if not selection` block. The run proceeds with nothing selected.
    """

    import argparse

    from scripts import abstention

    monkeypatch.setattr(abstention, "selection_for", lambda condition: [])
    args = argparse.Namespace(tasks="", seed=1)
    with pytest.raises(SystemExit, match="no task declares"):
        abstention.run_condition(args, "contradictory")


def test_naming_a_task_that_does_not_declare_the_condition_is_refused():
    """The other half of the same guard: a silent subset is a different suite.

    The pair is DERIVED rather than named. An earlier version named ts-append-only under
    `adjacent`, which nothing declared at the time and which ts-append-only declared hours later;
    before that, another test on this file named `contradictory` as the condition nothing declared
    and was invalidated the same way. A test written against the standing shape of the corpus is a
    test with an expiry date on it, and this file has now issued two.
    """

    from harness.damage import CONDITIONS
    from harness.tasks import discover_tasks
    from scripts.abstention import selection_for

    planted = [task.task_id for task in discover_tasks() if (task.path / "plants.json").is_file()]
    pair = next(
        (
            (condition, task_id)
            for condition in CONDITIONS
            for task_id in planted
            if task_id not in set(selection_for(condition))
        ),
        None,
    )
    if pair is None:
        pytest.skip("every planted task declares every condition, so there is no pair to refuse")
    condition, task_id = pair

    result = _run(
        ["--arms", "bare", "--conditions", condition, "--tasks", task_id, "--dry-run"]
    )
    combined = result.stdout + result.stderr
    assert "do not declare" in combined and task_id in combined


# ---------------------------------------------------------------------------------------
# the classification hook in pilot.py
# ---------------------------------------------------------------------------------------


def test_classification_reads_the_real_sandbox(tmp_path):
    """BEHAVIOURAL, against a sandbox built from the committed references.

    An earlier version of this test asserted that `outcome_for(` appeared in pilot's source. That
    passes even when the call is behind `if False:`, which a mutation proved, so it was testing
    that the code LOOKS right rather than that it works.
    """

    from harness.damage import Outcome
    from harness.sandbox import restore
    from harness.tasks import apply_reference, discover_tasks, run_checker
    from scripts.pilot import classify_cell

    task = next(t for t in discover_tasks() if t.task_id == "ts-tz-utc")

    damaged_dir = tmp_path / "damaged"
    restore(task.task_id, damaged_dir)
    apply_reference(task, "damaged_superseded", damaged_dir)
    ok, verdict = run_checker(task, damaged_dir)
    result = classify_cell(task, damaged_dir, "superseded", ok, verdict, "done")
    assert result["outcome"] == Outcome.DAMAGED.value, result
    assert result["condition"] == "superseded"
    assert result["damage_reason"]

    naive_dir = tmp_path / "naive"
    restore(task.task_id, naive_dir)
    apply_reference(task, "naive", naive_dir)
    ok, verdict = run_checker(task, naive_dir)
    result = classify_cell(task, naive_dir, "superseded", ok, verdict, "done")
    assert result["outcome"] == Outcome.NEUTRAL_FAILURE.value, (
        "a factless failure attributed to the plant would make damage indistinguishable from "
        "ordinary failure"
    )


def test_classification_is_off_unless_a_condition_is_named():
    """Every run before the abstention suite records pass or fail only, and must keep doing so."""

    from scripts.pilot import classify_cell

    assert classify_cell(None, None, "", True, "", "") == {}


def test_the_runner_is_wired_to_the_classifier():
    """A WIRING check, and labelled as one rather than dressed up as behavioural.

    `classify_cell` is tested against a real sandbox above. Whether `runner` actually calls it
    can only be established by running a session or by reading the source, and running a session
    costs an API call per assertion. So this reads the source, and its weakness is stated: it
    proves the call is present, not that it is reached.
    """

    runner_start = PILOT.index("async def runner(row, arm):")
    runner_end = PILOT.index("rows = [", runner_start)
    body = PILOT[runner_start:runner_end]
    assert "classify_cell(" in body, "runner() must call the classifier"
    assert "**condition_extra" in body, "its result must reach the record's metadata"


def test_abstention_is_judged_from_the_response(tmp_path):
    from harness.sandbox import restore
    from harness.tasks import apply_reference, discover_tasks, run_checker
    from scripts.pilot import classify_cell

    task = next(t for t in discover_tasks() if t.task_id == "ts-tz-utc")
    workdir = tmp_path / "s"
    restore(task.task_id, workdir)
    apply_reference(task, "naive", workdir)
    ok, verdict = run_checker(task, workdir)
    said = classify_cell(
        task, workdir, "absent", ok, verdict, "I could not find any record of a convention."
    )
    assert said["abstained"] is True and said["abstain_marker"]
    quiet = classify_cell(task, workdir, "absent", ok, verdict, "Updated the parser.")
    assert quiet["abstained"] is False


@needs_clean_preregistration
def test_a_corpus_without_a_manifest_is_refused(tmp_path):
    """BEHAVIOURAL. Mutation: dropping the manifest check. Arms would ingest a feed nothing has
    hashed, which is how two arms end up on different corpora with nothing reporting it."""

    empty = tmp_path / "no-manifest"
    empty.mkdir()
    result = subprocess.run(
        [sys.executable, "-m", "scripts.pilot", "--arms", "fs_grep,bare", "--tasks", "ts-tz-utc",
         "--seeds", "1", "--run-id", "unit-probe", "--corpus-root", str(empty)],
        cwd=str(REPO), capture_output=True, text=True, timeout=180,
        env={**os.environ, "OPENROUTER_API_KEY": "placeholder"}, check=False,
    )
    assert "holds no manifest.json" in result.stdout + result.stderr


# ---------------------------------------------------------------------------------------
# reading a finished condition back
# ---------------------------------------------------------------------------------------


def test_discarded_cells_are_excluded_from_the_analysis(tmp_path):
    """A discarded cell has no proven treatment, so it cannot carry an outcome. Mutation:
    ignoring admission.json, which would readmit every cell the gate threw out."""

    from scripts.abstention import load_cells

    run = tmp_path / "run"
    run.mkdir()
    rows = [
        {"task_id": "ts-tz-utc", "seed": 0, "arm": "bare", "success": True,
         "metadata": {"outcome": "solved"}},
        {"task_id": "ts-tz-utc", "seed": 1, "arm": "bare", "success": False,
         "metadata": {"outcome": "damaged"}},
    ]
    (run / "records.final.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    (run / "admission.json").write_text(
        json.dumps({"discarded_cells": [["ts-tz-utc", 1]]}), encoding="utf-8"
    )
    cells = load_cells(run, "superseded")
    assert len(cells) == 1
    assert cells[0].seed == 0


def test_a_missing_run_directory_yields_nothing_rather_than_raising(tmp_path):
    from scripts.abstention import load_cells

    assert load_cells(tmp_path / "absent", "absent") == []


@needs_clean_preregistration
def test_the_dry_run_assembles_a_real_corpus_and_executes_nothing():
    """The assembly is deterministic and cheap, so a dry run does it for real: that is what makes
    the dry run a check on the corpus rather than only on the command line."""

    result = _run(
        ["--run-id", "unit-probe", "--conditions", "absent", "--arms", "bare",
         "--seeds", "1", "--dry-run"],
        {"RECALL_DSN": None, "OPENROUTER_API_KEY": "placeholder"},
    )
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "session file(s) in the feed" in out
    assert "nothing was ingested, run or analysed" in out
    assert not (REPO / "results" / "unit-probe-absent").exists()


def test_an_unclassified_arm_is_refused_rather_than_silently_skipped():
    """Mutation: pass an arm that is in neither MEMORY_ARMS nor NON_MEMORY_ARMS.

    This exists because of `official-001`. `mempalace` was never added to MEMORY_ARMS, so the run
    published no search rate for it and never applied the 0.50 interpretability floor to it.
    Recomputed afterwards, its rate on `absent` was 0.545 against recall's 0.848: barely above the
    floor, and materially different from the arm it was being compared against.

    Nothing errored. The arm ran, produced records, and was simply absent from one table. A
    reader would have seen four rows where there should have been eight and had no reason to
    count. Refusing up front is the only version of this check that cannot be missed.
    """

    import pytest

    from scripts.abstention import _classify_arms

    _classify_arms(["bare", "claude_md", "recall", "mempalace"])  # must not raise

    with pytest.raises(SystemExit) as excinfo:
        _classify_arms(["bare", "recall", "brand_new_product"])
    assert "brand_new_product" in str(excinfo.value)


def test_retired_tasks_are_excluded_and_announced(capsys):
    """A task no arm has ever failed is dropped, and the drop is printed rather than silent.

    Both halves matter. official-001 spent 82.2% of its sessions on cells where every arm produced
    the same outcome, which is the reason for the exclusion. And the last time this suite dropped
    something quietly it was a whole product arm missing from MEMORY_ARMS, invisible in the
    artifact until someone counted rows. A grid that shrinks without saying so is that same
    failure with a different subject.
    """

    from scripts.abstention import RETIRED_TASKS, selection_for

    assert RETIRED_TASKS, "the retirement list must not be silently emptied"

    tasks = selection_for("absent")
    assert tasks, "retiring tasks must not empty a condition"
    for retired in RETIRED_TASKS:
        assert retired not in tasks, f"{retired} is retired and must not be selected"

    printed = capsys.readouterr().out
    for retired in RETIRED_TASKS:
        assert retired in printed, f"{retired} was dropped without saying so"
        assert RETIRED_TASKS[retired] in printed, "the reason must travel with the exclusion"

    quiet = selection_for("absent", announce=False)
    assert quiet == tasks
    assert not capsys.readouterr().out
