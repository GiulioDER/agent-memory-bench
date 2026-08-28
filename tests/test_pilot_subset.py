"""The task subset, the conditional DSN requirement, and --dry-run.

All three touch `scripts/pilot.py`, which is the instrument three preregistered runs used, so the
tests that matter here are the ones asserting nothing changed for an ordinary invocation: the
default task set is still every `ts-*` task, and a run including the recall arm still refuses to
start without a corpus.

## Most cases pass --dry-run, and that is a safety property rather than a convenience

Mutation testing removes a guard on purpose. If the guarded action is "run the grid", removing the
guard RUNS THE GRID: a mutation run of the DSN check did exactly that here, leaving 464 files under
`results/unit-probe` whose read-only git objects then defeated its own cleanup. Passing `--dry-run`
keeps each refusal observable while making it impossible for a mutation to execute a session.

TWO cases cannot use that protection, and both are scoped to one task and one seed so a mutated
pilot runs a session or two rather than a full grid:

* the dry-run test itself, whose mutation removes the exit being tested;
* the DSN refusal, which by design no longer fires under `--dry-run`. A dry run stops before any
  query, so requiring a database there defeats the point of a cheap check; that guard protects a
  REAL run and can only be tested by one.

Both clean up after themselves, because pilot writes per-task bundles under `results/<run-id>/cfg/`
before either check is reached.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _preregistration_dirty() -> bool:
    """Is `preregistration/` uncommitted, so pilot.py will refuse before reaching any check here?

    `assert_preregistered` runs first in main(), so while a record is being written every test in
    this file sees that refusal instead of the one it asserts. Skipping is right rather than
    working around it: the alternative is four failures every time a result is appended, which
    trains you to ignore this file exactly when it might be telling you something.
    """

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "preregistration/", "benchmarks/"],
            cwd=str(REPO), capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(result.stdout.strip())


needs_clean_preregistration = pytest.mark.skipif(
    _preregistration_dirty(),
    reason="preregistration/ is uncommitted, so pilot.py refuses before any check under test",
)


def _run(args: list[str], env_overrides: dict[str, str | None]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    for key, value in env_overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-m", "scripts.pilot", *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        # Most cases here expect a non-zero exit; the assertions are about which refusal it is.
        check=False,
    )


def _force_rmtree(target: Path) -> None:
    """Remove a run directory, including the read-only git objects a sandbox leaves on Windows."""

    def _clear_readonly(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    if target.exists():
        shutil.rmtree(target, onexc=_clear_readonly)


@pytest.fixture
def clean_unit_probe():
    """pilot builds bundles under results/<run-id>/cfg/ before the DSN check refuses, so a test
    that reaches that refusal leaves files behind."""

    target = REPO / "results" / "unit-probe"
    _force_rmtree(target)
    yield
    _force_rmtree(target)


@pytest.fixture
def probe_run_dir():
    """Yield a run id and guarantee its directory is gone afterwards, mutated or not."""

    run_id = "unit-probe-dry-run"
    target = REPO / "results" / run_id
    _force_rmtree(target)
    yield run_id, target
    _force_rmtree(target)


@needs_clean_preregistration
def test_a_bare_only_run_does_not_require_a_database():
    """Mutation: restoring the unconditional DSN check. A bare-only calibration then cannot run
    without standing up a database it never queries.

    The API key is SET here on purpose. An earlier version of this test unset it too, so the run
    exited on the key check before ever reaching the DSN check, and passed under the very mutation
    it was written to catch. A deliberately unknown task id is what stops the run: that check sits
    after the DSN check, so reaching it proves the DSN check let a bare run through.
    """

    result = _run(
        ["--arms", "bare", "--tasks", "ts-does-not-exist", "--run-id", "unit-probe", "--dry-run"],
        {"RECALL_DSN": None, "OPENROUTER_API_KEY": "placeholder"},
    )
    output = result.stdout + result.stderr
    assert "RECALL_DSN is not set" not in output
    assert "unknown task(s)" in output


@needs_clean_preregistration
def test_a_run_with_the_recall_arm_still_refuses_without_a_corpus(clean_unit_probe):
    """The half of the old check that must survive: a recall arm with no DSN is a run whose
    treatment is silently absent, which is what the admission gate exists to prevent."""

    # NOT --dry-run, deliberately. A dry run resolves the grid and stops before any query, so the
    # DSN requirement is skipped there on purpose; this guard protects a REAL run and can only be
    # tested by one. It is safe: the check sits well before the runner, so an unmutated pilot exits
    # without starting a session. Scoped to one task and one seed so that a MUTATED pilot, which
    # would fall through to the grid, runs two unauthenticated sessions rather than a full grid.
    result = _run(
        ["--arms", "bare,recall", "--tasks", "ts-tz-utc", "--seeds", "1", "--run-id", "unit-probe"],
        {"RECALL_DSN": None, "OPENROUTER_API_KEY": "placeholder"},
    )
    assert "RECALL_DSN is not set" in result.stdout + result.stderr


@needs_clean_preregistration
def test_an_unknown_task_id_is_refused():
    """Mutation: filtering silently. A typo would then run a smaller grid than asked for and
    report it under the same run id."""

    result = _run(
        [
            "--arms", "bare",
            "--tasks", "ts-json-sorted,ts-does-not-exist",
            "--run-id", "unit-probe",
            "--dry-run",
        ],
        {"RECALL_DSN": None, "OPENROUTER_API_KEY": "placeholder"},
    )
    assert "unknown task(s)" in result.stdout + result.stderr
    assert "ts-does-not-exist" in result.stdout + result.stderr


@needs_clean_preregistration
def test_a_dry_run_writes_nothing_and_executes_nothing(probe_run_dir):
    """Mutation: moving the dry-run exit below the run directory creation, or removing it.

    This exists because of a real incident. Checking a command line by running it with a
    placeholder API key executed the entire 36-session grid, produced 36 discarded cells and burned
    the run id, which had to be quarantined as `results/midband-001-invalid-no-api-key`. Spend was
    $0.00 because every session failed to authenticate, so the cost was a run id and an hour of
    care rather than money. `--dry-run` is the check that should have existed.

    Scoped to one task and one seed: this is the one test whose mutation can still start a
    session, so the blast radius is kept to one.
    """

    run_id, target = probe_run_dir
    result = _run(
        ["--arms", "bare", "--tasks", "ts-json-sorted", "--seeds", "1", "--run-id", run_id, "--dry-run"],
        {"RECALL_DSN": None, "OPENROUTER_API_KEY": "placeholder"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "would run 1 session(s)" in result.stdout
    assert not target.exists(), "a dry run created the run directory"


def test_the_default_task_set_is_unchanged():
    """No --tasks means every ts-* task, exactly as the three preregistered runs invoked it."""

    source = (REPO / "scripts" / "pilot.py").read_text(encoding="utf-8")
    assert 'parser.add_argument(\n        "--tasks",\n        default="",' in source, (
        "the subset must default to empty, or an ordinary invocation silently changes its grid"
    )
    assert 'tasks = [task for task in discover_tasks() if task.task_id.startswith("ts-")]' in source
