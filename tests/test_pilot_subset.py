"""The task subset and the conditional DSN requirement added for the mid-band calibration.

Both changes touch `scripts/pilot.py`, which is the instrument three preregistered runs used, so
the tests that matter here are the ones asserting that nothing changed for an ordinary
invocation: the default task set is still every `ts-*` task, and a run that includes the recall
arm still refuses to start without a corpus.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(args: list[str], env_overrides: dict[str, str | None]) -> subprocess.CompletedProcess:
    import os

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
        timeout=180,
        env=env,
        # Every case here expects a non-zero exit; the assertions are about which refusal it is.
        check=False,
    )


def test_a_bare_only_run_does_not_require_a_database():
    """Mutation: restoring the unconditional DSN check. A bare-only calibration then cannot run
    without standing up a database it never queries.

    The API key is SET here on purpose. An earlier version of this test unset it too, so the run
    exited on the key check before ever reaching the DSN check, and the test passed under the very
    mutation it was written to catch. A deliberately unknown task id is what stops the run: that
    check sits after the DSN check, so reaching it proves the DSN check let a bare run through,
    and nothing is executed.
    """

    result = _run(
        ["--arms", "bare", "--tasks", "ts-does-not-exist", "--run-id", "unit-probe"],
        {"RECALL_DSN": None, "OPENROUTER_API_KEY": "placeholder"},
    )
    output = result.stdout + result.stderr
    assert "RECALL_DSN is not set" not in output
    assert "unknown task(s)" in output


def test_a_run_with_the_recall_arm_still_refuses_without_a_corpus():
    """The half of the old check that must survive: a recall arm with no DSN is a run whose
    treatment is silently absent, which is exactly what the admission gate exists to prevent."""

    result = _run(
        ["--arms", "bare,recall", "--run-id", "unit-probe"],
        {"RECALL_DSN": None, "OPENROUTER_API_KEY": "placeholder"},
    )
    assert "RECALL_DSN is not set" in result.stdout + result.stderr


def test_an_unknown_task_id_is_refused():
    """Mutation: filtering silently. A typo would then run a smaller grid than asked for and
    report it under the same run id."""

    result = _run(
        ["--arms", "bare", "--tasks", "ts-json-sorted,ts-does-not-exist", "--run-id", "unit-probe"],
        {"RECALL_DSN": None, "OPENROUTER_API_KEY": "placeholder"},
    )
    assert "unknown task(s)" in result.stdout + result.stderr
    assert "ts-does-not-exist" in result.stdout + result.stderr


def test_the_default_task_set_is_unchanged():
    """No --tasks means every ts-* task, exactly as the three preregistered runs invoked it."""

    source = (REPO / "scripts" / "pilot.py").read_text(encoding="utf-8")
    assert 'parser.add_argument(\n        "--tasks",\n        default="",' in source, (
        "the subset must default to empty, or an ordinary invocation silently changes its grid"
    )
    assert 'tasks = [task for task in discover_tasks() if task.task_id.startswith("ts-")]' in source
