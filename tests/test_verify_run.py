"""The verifier has to FAIL on a doctored artifact, or it is decoration.

Every test here was written by breaking something on purpose and watching the named check go red.
A verifier nobody has watched fail has not been tested, and this one exists specifically so a
reader who distrusts the benchmark has something better than the author's word.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.verify_run import verify


def _write(run_dir: Path, records: list[dict], admission: dict, costs: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "records.final.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
    )
    (run_dir / "admission.json").write_text(json.dumps(admission), encoding="utf-8")
    (run_dir / "costs.json").write_text(json.dumps(costs), encoding="utf-8")
    streams = run_dir / "streams"
    streams.mkdir(exist_ok=True)
    for r in records:
        (streams / f"{r['task_id']}.s{r['seed']}.{r['arm']}.jsonl.gz").write_bytes(b"")


def _record(task: str, seed: int, arm: str, *, inp: int = 100, out: int = 10) -> dict:
    return {
        "task_id": task,
        "seed": seed,
        "arm": arm,
        "success": True,
        "user_input": "x",
        "response": "y",
        "input_tokens": inp,
        "output_tokens": out,
        "metadata": {},
    }


@pytest.fixture
def good_run(tmp_path):
    """One clean two-arm run whose summaries genuinely follow from its records."""

    records = [
        _record("ts-a", 0, "bare"),
        _record("ts-a", 0, "recall"),
        _record("ts-b", 0, "bare"),
        _record("ts-b", 0, "recall"),
    ]
    admission = {
        "admitted_cells": 2,
        "discarded_cells": [],
        "required_arms": ["bare", "recall"],
        "verdicts": [
            {"task_id": r["task_id"], "seed": r["seed"], "arm": r["arm"], "admitted": True,
             "reasons": []}
            for r in records
        ],
    }
    costs = {"total_sessions": 4, "total_tokens": 440}
    run_dir = tmp_path / "verify-001"
    _write(run_dir, records, admission, costs)
    return run_dir


def test_a_clean_run_verifies(good_run):
    """The control. If this ever fails, every other test here is meaningless."""

    f = verify(good_run)
    assert not f.bad, f.bad


def test_a_doctored_token_total_is_caught(good_run):
    """Mutation: publish a token total that the records do not add up to.

    This is the headline check. Inflating a cost artifact after the fact is the cheapest possible
    way to lie about a benchmark, and it is invisible to a reader without exactly this.
    """

    costs = json.loads((good_run / "costs.json").read_text(encoding="utf-8"))
    costs["total_tokens"] = 999_999
    (good_run / "costs.json").write_text(json.dumps(costs), encoding="utf-8")

    f = verify(good_run)
    assert any("total tokens" in line for line in f.bad), f.bad


def test_a_dropped_session_is_caught(good_run):
    """Mutation: delete one arm's record from an admitted cell.

    Quietly dropping the arm that did badly is the second cheapest way to lie, and it leaves the
    cell looking admitted while no longer being paired.
    """

    path = good_run / "records.final.jsonl"
    kept = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not ('"ts-b"' in line and '"recall"' in line)
    ]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    f = verify(good_run)
    assert any("required arm" in line for line in f.bad), f.bad


def test_a_discard_that_no_verdict_supports_is_caught(good_run):
    """Mutation: discard a cell whose sessions were all admitted.

    A cell discarded without a verdict behind it is an unexplained exclusion, which is how an
    inconvenient result leaves a dataset without leaving a trace.
    """

    admission = json.loads((good_run / "admission.json").read_text(encoding="utf-8"))
    admission["discarded_cells"] = [["ts-a", 0]]
    admission["admitted_cells"] = 1
    (good_run / "admission.json").write_text(json.dumps(admission), encoding="utf-8")

    f = verify(good_run)
    assert any("re-derives" in line for line in f.bad), f.bad


def test_an_unexplained_discard_is_caught(good_run):
    """Mutation: mark a session inadmissible while giving no reason for it."""

    admission = json.loads((good_run / "admission.json").read_text(encoding="utf-8"))
    admission["verdicts"][0]["admitted"] = False
    admission["verdicts"][0]["reasons"] = []
    admission["discarded_cells"] = [["ts-a", 0]]
    admission["admitted_cells"] = 1
    (good_run / "admission.json").write_text(json.dumps(admission), encoding="utf-8")

    f = verify(good_run)
    assert any("states a reason" in line for line in f.bad), f.bad


def test_summaries_without_records_cannot_be_checked(good_run):
    """Mutation: publish the summaries and withhold the sessions.

    This is not hypothetical. `abstention-001` was published exactly this way, with an
    admission.json and a costs.json and no records at all, and nothing said so until this ran.
    """

    (good_run / "records.final.jsonl").unlink()
    f = verify(good_run)
    assert any("NOTHING CAN BE CHECKED" in line for line in f.bad), f.bad


def test_missing_streams_are_reported(good_run):
    """Mutation: remove the session streams.

    Records alone can be checked against each other but not against the sessions that produced
    them, so their absence is a finding rather than a detail.
    """

    for p in (good_run / "streams").glob("*.jsonl.gz"):
        p.unlink()
    (good_run / "streams").rmdir()

    f = verify(good_run)
    assert any("streams" in line for line in f.bad), f.bad


def test_the_published_runs_that_carry_records_still_verify():
    """The real artifacts, not fixtures. Guards against a schema drift that silently passes.

    Skipped rather than failed when a checkout has no results, so this is runnable anywhere.
    """

    results = REPO / "results"
    candidates = [
        d
        for d in sorted(results.iterdir())
        if d.is_dir() and (d / "records.final.jsonl").is_file() and (d / "costs.json").is_file()
    ] if results.is_dir() else []
    if not candidates:
        pytest.skip("no published runs with records in this checkout")

    for run_dir in candidates:
        f = verify(run_dir)
        recompute = [
            line
            for line in f.bad
            if "total tokens" in line or "session count" in line or "re-derives" in line
        ]
        assert not recompute, f"{run_dir.name}: {recompute}"


def test_a_timed_out_session_may_lack_its_stream(good_run):
    """A session killed at the timeout never flushes a stream, and that is not a defect.

    Measured on `official-001`: four sessions across three conditions hit
    `ClaudeSessionTimeout: claude exceeded timeout_s=600.0`, leaving a record with the error and
    no stream. An earlier version of the stream check demanded one stream per record and reported
    three of the four conditions as defective for behaving exactly as the protocol says they
    should. A verifier that cries wolf trains the reader to skim past the FAIL that matters.
    """

    stream = next((good_run / "streams").glob("ts-b.s0.recall*"))
    stream.unlink()
    path = good_run / "records.final.jsonl"
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["task_id"] == "ts-b" and record["arm"] == "recall":
            record["error"] = "ClaudeSessionTimeout: claude exceeded timeout_s=600.0"
            record["success"] = False
        lines.append(json.dumps(record))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    f = verify(good_run)
    assert not f.bad, f.bad
    assert any("explained by a recorded error" in line for line in f.ok), f.ok


def test_a_missing_stream_with_no_error_is_still_caught(good_run):
    """The other half: silence is not an explanation.

    Without this, the fix above would have turned a real check into no check at all, since every
    absent stream would pass by simply not being accounted for.
    """

    next((good_run / "streams").glob("ts-b.s0.recall*")).unlink()
    f = verify(good_run)
    assert any("no recorded" in line for line in f.bad), f.bad
