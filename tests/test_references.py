"""The discrimination gate every task must pass before it may cost agent sessions.

For every task directory carrying a reference/ pair, CI asserts three things against the real
checker and the real fixture:

- a **do-nothing** sandbox fails (a non-answer must never score),
- the **naive** reference (competent, without the governing fact) fails,
- the **informed** reference (with the fact) passes.

A task failing any of these is broken evidence, not a harder task.
"""

import pytest

from harness.sandbox import restore
from harness.tasks import apply_reference, discover_tasks, run_checker

TASKS = [task for task in discover_tasks() if task.reference_dir.is_dir()]


def _ids(tasks):
    return [task.task_id for task in tasks]


@pytest.mark.parametrize("task", TASKS, ids=_ids(TASKS))
def test_do_nothing_scores_zero(task, tmp_path):
    workdir = tmp_path / "sandbox"
    restore(task.task_id, workdir)
    ok, verdict = run_checker(task, workdir)
    assert not ok, f"{task.task_id}: an untouched sandbox passed the checker: {verdict}"


@pytest.mark.parametrize("task", TASKS, ids=_ids(TASKS))
def test_naive_reference_fails(task, tmp_path):
    workdir = tmp_path / "sandbox"
    restore(task.task_id, workdir)
    apply_reference(task, "naive", workdir)
    ok, verdict = run_checker(task, workdir)
    assert not ok, (
        f"{task.task_id}: the naive solution passed ({verdict}); the task no longer "
        f"discriminates on its governing fact"
    )


@pytest.mark.parametrize("task", TASKS, ids=_ids(TASKS))
def test_informed_reference_passes(task, tmp_path):
    workdir = tmp_path / "sandbox"
    restore(task.task_id, workdir)
    apply_reference(task, "informed", workdir)
    ok, verdict = run_checker(task, workdir)
    assert ok, f"{task.task_id}: the informed solution failed: {verdict}"
