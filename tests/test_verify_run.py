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

    🔁 The example this docstring used to give was wrong, corrected 2026-09-02. It said
    `abstention-001` was published exactly this way, with an admission.json and a costs.json and
    no records at all. Its records were published all along as the sibling file
    `results/abstention-001-<condition>-records.jsonl`, and `_load_records` only looked inside the
    run directory, so the tool reported missing evidence for evidence it could not find.

    The mutation this test performs is still the one that matters, and it is now the only source
    of that message: no published run produces it.
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


# ---------------------------------------------------------------------------------------------
# The endpoints check. Added 2026-08-30 after an audit found it could not fail.
#
# It read `f.check(set(got) <= set(want) or bool(got), ...)`. `endpoints()` never returns an empty
# dict, so `bool(got)` was a constant True: the published file was parsed and thrown away. Four
# independent verification passes each fabricated a published endpoints file and got a `pass`,
# including one whose every number was invented and one that was literally `{}`.
#
# This section had NO coverage before, and that is why. The only fixture was `good_run`, named
# `verify-001`, so `_condition_of` returned None and the whole branch was unreachable from the
# suite. A fixture whose name ends in a condition is what makes these tests possible at all.
# ---------------------------------------------------------------------------------------------


def _harm_record(task: str, seed: int, arm: str, outcome: str) -> dict:
    record = _record(task, seed, arm)
    record["metadata"] = {"outcome": outcome}
    return record


@pytest.fixture
def harm_run(tmp_path):
    """A one-condition harm-suite run beside the endpoints file it published.

    Two tasks, two arms, `bare` as reference. `ts-b` is damaged under `recall` while `bare`
    solved it, so the run has a non-zero damage rate and the published file has a number worth
    doctoring.
    """

    from harness.abstention import cells_from_records
    from scripts.verify_run import endpoints as _endpoints

    # Real task ids, because endpoint 2 filters on `stratum_of`, which is a lookup over the
    # actual task set: a fixture with invented ids lands entirely in BENEFIT_ONLY and publishes
    # an EMPTY `2_damage_rate_by_condition`, so a test doctoring that block would pass without
    # ever exercising the comparison.
    damage_only, two_sided = "ts-append-only", "ts-bom-merge"
    records = [
        _harm_record(damage_only, 0, "bare", "solved"),
        _harm_record(damage_only, 0, "recall", "damaged"),
        _harm_record(two_sided, 0, "bare", "solved"),
        _harm_record(two_sided, 0, "recall", "solved"),
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
    run_dir = tmp_path / "verify-002-absent"
    _write(run_dir, records, admission, costs)

    truthful = _endpoints(cells_from_records(records, "absent"), ["bare", "recall"])
    truthful["conditions"] = ["absent"]
    (tmp_path / "verify-002-endpoints.json").write_text(
        json.dumps(truthful, indent=1), encoding="utf-8"
    )
    return run_dir


def _endpoints_path(run_dir: Path) -> Path:
    return run_dir.parent / "verify-002-endpoints.json"


def _published(run_dir: Path) -> dict:
    return json.loads(_endpoints_path(run_dir).read_text(encoding="utf-8"))


def _republish(run_dir: Path, doc: dict) -> None:
    _endpoints_path(run_dir).write_text(json.dumps(doc, indent=1), encoding="utf-8")


def _endpoint_failures(run_dir: Path) -> list[str]:
    return [line for line in verify(run_dir).bad if "endpoints" in line]


def test_an_honest_endpoints_file_verifies(harm_run):
    """Control. Without this the rest could pass by failing on everything."""

    assert _endpoint_failures(harm_run) == []


def test_a_doctored_damage_rate_is_caught(harm_run):
    """RED before the fix: `bool(got)` made the check true whatever the published number said."""

    doc = _published(harm_run)
    doc["arms"]["recall"]["2_damage_rate_by_condition"]["absent"]["damage_rate"] = 0.99
    _republish(harm_run, doc)
    assert _endpoint_failures(harm_run), "a fabricated damage rate verified clean"


def test_a_doctored_net_harm_is_caught(harm_run):
    """The HEADLINE number, pooled across conditions, recomputed from the sibling run dirs.

    RED twice over: once for the tautology, and once for the first version of this fix, which
    skipped `1_net_harm_by_stratum` as unrecomputable from one condition and therefore let a
    sign-flipped net harm through while catching everything else.
    """

    doc = _published(harm_run)
    for stratum in doc["arms"]["recall"]["1_net_harm_by_stratum"].values():
        stratum["net_harm"] = -0.999
        stratum["harmed"] = 999
    _republish(harm_run, doc)
    assert _endpoint_failures(harm_run), "a fabricated net harm verified clean"


def test_a_perturbation_inside_the_old_cost_tolerance_is_caught(harm_run):
    """An endpoint is a deterministic recomputation, so it reconciles exactly or not at all.

    RED before the fix, and still red under `_close`'s 0.5% band, which is right for a cost total
    that accumulates float error over thousands of additions and wrong for this. Measured: a
    net_harm shifted by 0.001 verified clean under the loose tolerance.
    """

    doc = _published(harm_run)
    block = doc["arms"]["recall"]["2_damage_rate_by_condition"]["absent"]
    block["damage_rate"] = block["damage_rate"] + 0.001
    _republish(harm_run, doc)
    assert _endpoint_failures(harm_run), "a 0.001 perturbation verified clean"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="empty-object"),
        pytest.param({"reference_arm": "bare", "arms": {}}, id="no-arms"),
        pytest.param({"reference_arm": "bare", "arms": {"not-an-arm": {}}}, id="arm-never-ran"),
        pytest.param({"reference_arm": "claude_md", "arms": {}}, id="wrong-reference-arm"),
    ],
)
def test_a_structurally_wrong_endpoints_file_is_caught(harm_run, payload):
    """RED before the fix: every one of these verified clean, `{}` included."""

    _republish(harm_run, payload)
    assert _endpoint_failures(harm_run), "a structurally wrong endpoints file verified clean"


@pytest.mark.parametrize("payload", ["null", "0", '[{"a": 1}]', '"a string"'])
def test_a_malformed_endpoints_file_fails_one_run_rather_than_the_sweep(harm_run, payload):
    """RED before the fix: `set(want)` raised TypeError, aborting every later run in `--all`."""

    _endpoints_path(harm_run).write_text(payload, encoding="utf-8")
    findings = verify(harm_run)  # must not raise
    assert findings.bad, "a malformed endpoints file was not reported"


def test_endpoints_without_an_admission_report_do_not_raise(harm_run):
    """RED before the fix: FileNotFoundError escaped verify() and killed the whole sweep.

    The admission read sat inside a branch guarded on the ENDPOINTS file existing, not on the
    admission file.
    """

    (harm_run / "admission.json").unlink()
    findings = verify(harm_run)  # must not raise

    # The specific NEW message. `"admission" in line` was satisfied by a pre-existing skip
    # ("no admission.json to check") that fires whether or not the endpoints guard exists, so it
    # would have stayed green if the endpoints branch were ever moved above the admission check.
    assert any(
        "endpoints published but no admission.json" in line for line in findings.skipped
    ), f"the endpoints branch did not state why it could not run; skipped={findings.skipped}"


def test_the_archive_directory_is_not_treated_as_a_run(tmp_path, monkeypatch):
    """RED before the fix: `results/archive/` went red as a run that never was.

    scripts/archive_partial.py parks an interrupted grid there deliberately. Failing on it makes
    `--all` exit 1 on a healthy repository, which is the crying-wolf this module warns about
    ninety lines above the check that was doing it.
    """

    from scripts import verify_run as vr

    results = tmp_path / "results"
    (results / "archive" / "20260830-run-absent" / "results").mkdir(parents=True)
    (results / "logs").mkdir()
    real = results / "run-001-absent"
    real.mkdir()
    (real / "records.final.jsonl").write_text("", encoding="utf-8")

    # The REAL selector, not a copy of it. The first version of this test restated main()'s
    # comprehension in its own body and stayed green with the fix deleted, which is the defect
    # class this whole round is about.
    targets = vr.run_targets(results)
    assert [d.name for d in targets] == ["run-001-absent"], (
        "only `archive` and `logs` are excluded; a directory that merely LOOKS empty must still "
        "be reported, because a gutted run directory is exactly what this verifier exists to "
        "catch"
    )


def test_a_leaderboard_rollup_is_not_a_run_but_a_gutted_directory_still_is(tmp_path):
    """The roll-up is excluded by what it HAS, never by what it lacks.

    A run measured per condition publishes its sessions under `<run>-<condition>/` and its
    leaderboard summary under `<run>/`. That summary directory carries no sessions and never
    will, so reporting it as unverifiable is a false alarm on the one name a reader checks
    first. A directory carrying neither summary nor records is a different thing entirely: it is
    a run whose evidence went missing, and it must still be reported.
    """
    from scripts import verify_run as vr

    results = tmp_path / "results"
    rollup = results / "official-999"
    rollup.mkdir(parents=True)
    (rollup / "leaderboard_summary.json").write_text("{}", encoding="utf-8")

    gutted = results / "official-999-present"
    gutted.mkdir()

    both = results / "official-999-absent"
    both.mkdir()
    (both / "leaderboard_summary.json").write_text("{}", encoding="utf-8")
    (both / "records.final.jsonl").write_text("", encoding="utf-8")

    # A run that lost its records and kept the rest. The tempting predicate, "has a summary and
    # no records", would hide this one, and it is the single artifact this verifier exists to
    # catch.
    hollowed = results / "official-999-adjacent"
    hollowed.mkdir()
    (hollowed / "leaderboard_summary.json").write_text("{}", encoding="utf-8")
    (hollowed / "admission.json").write_text("{}", encoding="utf-8")

    names = [d.name for d in vr.run_targets(results)]
    assert "official-999" not in names, "a summary-only roll-up is not a run and must not be checked"
    assert "official-999-present" in names, (
        "a directory with neither summary nor records is a gutted run, and excluding it would "
        "turn this verifier into the thing it warns about"
    )
    assert "official-999-absent" in names, (
        "a directory that carries records is a run even when a summary sits beside them"
    )
    assert "official-999-adjacent" in names, (
        "a run whose records went missing must still be reported; only a LONE summary file is a "
        "roll-up"
    )


def test_every_known_missing_streams_note_still_describes_a_failing_run():
    """A ratchet on the annotations, so a note cannot outlive the thing it explains.

    `KNOWN_MISSING_STREAMS` annotates failures rather than silencing them, which is only honest
    while every entry still corresponds to a run that actually fails. If someone publishes a run's
    streams, this goes red and demands the note be deleted; if a run is renamed or dropped, the
    same. Without it the notes decay into folklore that outlives its subject, which is precisely
    how this repository ended up telling readers that abstention-001 had no records when it had 99
    per condition all along.
    """
    from scripts import verify_run as vr

    results = vr.REPO / "results"
    stale = []
    for name, reason in vr.KNOWN_MISSING_STREAMS.items():
        assert reason.strip(), f"{name} carries an empty reason"
        run_dir = results / name
        if not run_dir.is_dir():
            stale.append(f"{name}: no such run directory")
            continue
        if not vr.verify(run_dir).bad:
            stale.append(f"{name}: verifies cleanly now, so the note is stale")
    assert not stale, (
        "KNOWN_MISSING_STREAMS describes runs that no longer match it:\n  "
        + "\n  ".join(stale)
        + "\nDelete the entry rather than keeping an explanation for a failure that is gone."
    )


def test_the_retrieval_directory_is_not_treated_as_a_run():
    """It holds retrieval_probe artifacts, not agent sessions, so it can never have evidence."""
    from scripts import verify_run as vr

    results = vr.REPO / "results"
    if not (results / "retrieval").is_dir():
        pytest.skip("no retrieval probe directory in this checkout")
    assert "retrieval" not in {d.name for d in vr.run_targets(results)}
