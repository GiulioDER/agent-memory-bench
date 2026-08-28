"""Guards on the two analysis paths, each watched red against the mutation its docstring names.

Both exist because the retry landed. Before it, results/<run>/records.jsonl held one line per cell
and arm and the two files were interchangeable; now it holds one line per ATTEMPT, so pointing an
analyzer at it double counts every retried session. And an analyzer that never reads admission.json
scores cells the gate refused, which is a different experiment from the frozen one.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness.schema import SessionRecord
from scripts.analyze_diagnostic import compare, discarded_cells
from scripts.failure_taxonomy import classify, taxonomy

REPO = Path(__file__).resolve().parents[1]
ARMS = ("claude_md", "recall", "oracle_memory", "recall_prefetch")


def _record(task: str, seed: int, arm: str, success: bool = True, **metadata) -> SessionRecord:
    return SessionRecord(
        task_id=task,
        arm=arm,
        seed=seed,
        success=success,
        memory_call_count=metadata.pop("memory_call_count", 0),
        retrieved_contexts=tuple(metadata.pop("retrieved_contexts", ())),
        metadata=metadata,
    )


def _grid(tasks=("ts-a", "ts-b"), seeds=(0,)) -> list[SessionRecord]:
    return [_record(t, s, arm) for t in tasks for s in seeds for arm in ARMS]


# ---------------------------------------------------------------------------------------
# analyze_diagnostic
# ---------------------------------------------------------------------------------------


def test_a_clean_grid_compares_without_complaint():
    analysis = compare(_grid())
    assert analysis["arms"]["recall"]["n"] == 2


def test_two_records_for_one_cell_and_arm_are_refused():
    """Mutation: dropping the Counter guard. records.jsonl then scores a retried session twice,
    and the arm that needed the retry gains a success it did not earn."""

    records = _grid() + [_record("ts-a", 0, "recall")]
    with pytest.raises(ValueError, match="records.final.jsonl"):
        compare(records)


def test_the_refusal_names_the_offending_cell():
    records = _grid() + [_record("ts-b", 0, "oracle_memory")]
    with pytest.raises(ValueError, match=r"ts-b"):
        compare(records)


def test_discarded_cells_are_read_as_task_and_seed_pairs(tmp_path):
    path = tmp_path / "admission.json"
    path.write_text(json.dumps({"discarded_cells": [["ts-a", 1], ["ts-b", 0]]}), encoding="utf-8")
    assert discarded_cells(path) == {("ts-a", 1), ("ts-b", 0)}


def _write_run(tmp_path, records, admission=None) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    (run / "records.final.jsonl").write_text(
        "".join(json.dumps(r.to_dict(), sort_keys=True) + "\n" for r in records), encoding="utf-8"
    )
    if admission is not None:
        (run / "admission.json").write_text(json.dumps(admission), encoding="utf-8")
    return run


def _run_analyzer(run: Path, out: Path, *extra) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.analyze_diagnostic",
            str(run / "records.final.jsonl"),
            "--out-dir",
            str(out),
            *extra,
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_missing_admission_report_is_refused_rather_than_ignored(tmp_path):
    """Mutation: falling through to scoring everything when admission.json is absent. The
    preregistration carries an exclusions list, and silently ignoring it reports a different
    experiment under the frozen one's name."""

    run = _write_run(tmp_path, _grid())
    result = _run_analyzer(run, tmp_path / "out")
    assert result.returncode != 0
    assert "refusing to score cells the gate never admitted" in (result.stderr + result.stdout)


def test_scoring_everything_is_available_but_must_be_asked_for(tmp_path):
    run = _write_run(tmp_path, _grid())
    result = _run_analyzer(run, tmp_path / "out", "--allow-unadmitted")
    assert result.returncode == 0, result.stderr
    analysis = json.loads((tmp_path / "out" / "diagnostic_analysis.json").read_text("utf-8"))
    assert analysis["arms"]["recall"]["n"] == 2
    assert analysis["admission"]["source"] is None


def test_discarded_cells_are_excluded_from_every_arm(tmp_path):
    """Mutation: filtering only the arm that failed admission. A paired design scores a CELL, so
    dropping one arm of a discarded cell leaves the other three arms scored on a cell that has no
    comparison group."""

    run = _write_run(tmp_path, _grid(seeds=(0, 1)), admission={"discarded_cells": [["ts-a", 1]]})
    result = _run_analyzer(run, tmp_path / "out")
    assert result.returncode == 0, result.stderr
    analysis = json.loads((tmp_path / "out" / "diagnostic_analysis.json").read_text("utf-8"))
    for arm in ARMS:
        assert analysis["arms"][arm]["n"] == 3, f"{arm} kept a discarded cell"
    assert analysis["admission"]["discarded_cells"] == [["ts-a", 1]]
    assert analysis["admission"]["records_scored"] == 12


# ---------------------------------------------------------------------------------------
# failure_taxonomy
# ---------------------------------------------------------------------------------------


def test_a_session_that_never_called_memory_is_the_first_class():
    record = _record("ts-a", 0, "recall", success=False).to_dict()
    assert classify(record) == "did not search"


def test_searching_without_the_governing_memo_is_its_own_class():
    record = _record(
        "ts-a", 0, "recall", success=False, memory_call_count=2,
        retrieved_contexts=("sessions__ts-other__p01.md",),
    ).to_dict()
    assert classify(record) == "searched, governing memo not reached"


def test_the_governing_memo_reached_splits_on_the_outcome():
    """Mutation: classifying on success before checking reach. Then every failure that DID reach
    memory is filed as a retrieval failure, and the dominant class in pilot-004 disappears."""

    kwargs = {
        "memory_call_count": 1,
        "retrieved_contexts": ("corpus/sessions__ts-a__p01.md",),
    }
    failed = _record("ts-a", 0, "recall", success=False, **kwargs).to_dict()
    solved = _record("ts-a", 0, "recall", success=True, **kwargs).to_dict()
    assert classify(failed) == "reached it, still failed"
    assert classify(solved) == "reached it, solved"


def test_an_mcp_tool_result_counts_as_reaching_it():
    record = _record("ts-a", 0, "recall", success=True, memory_call_count=1).to_dict()
    record["tool_calls"] = [
        {"name": "mcp__recall__recall_search", "output": "... sessions__ts-a__p01.md ..."}
    ]
    assert classify(record) == "reached it, solved"


def test_discarded_cells_never_enter_the_taxonomy():
    records = [
        _record("ts-a", 0, "recall", success=True, memory_call_count=1).to_dict(),
        _record("ts-a", 1, "recall", success=False).to_dict(),
    ]
    result = taxonomy(records, discarded={("ts-a", 1)}, arm="recall")
    assert result["admitted_sessions"] == 1
    assert result["classes"]["did not search"]["n"] == 0


def test_the_shares_add_up_to_the_admitted_sessions():
    records = [
        _record("ts-a", seed, "recall", success=seed % 2 == 0, memory_call_count=seed).to_dict()
        for seed in range(4)
    ]
    result = taxonomy(records, discarded=set(), arm="recall")
    assert sum(row["n"] for row in result["classes"].values()) == result["admitted_sessions"] == 4
