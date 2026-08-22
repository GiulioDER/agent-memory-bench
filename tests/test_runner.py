import asyncio

import pytest

from harness.runner import run_grid
from harness.schema import SessionRecord


def _ok(row, arm):
    return SessionRecord(
        task_id=str(row["task_id"]), arm=arm, seed=int(row.get("seed", 0)), success=True
    )


def test_run_grid_runs_every_arm_for_every_cell():
    async def runner(row, arm):
        return _ok(row, arm)

    rows = [{"task_id": "t1", "seed": 0}, {"task_id": "t1", "seed": 1}]
    records = asyncio.run(run_grid(rows, ("bare", "claude_md", "recall"), runner))
    assert len(records) == 6
    assert {(r.task_id, r.seed, r.arm) for r in records} == {
        ("t1", 0, "bare"),
        ("t1", 0, "claude_md"),
        ("t1", 0, "recall"),
        ("t1", 1, "bare"),
        ("t1", 1, "claude_md"),
        ("t1", 1, "recall"),
    }


def test_runner_exception_becomes_error_record():
    async def runner(row, arm):
        if arm == "recall":
            raise RuntimeError("server died")
        return _ok(row, arm)

    records = asyncio.run(run_grid([{"task_id": "t1"}], ("bare", "recall"), runner))
    by_arm = {r.arm: r for r in records}
    assert by_arm["bare"].success
    assert not by_arm["recall"].success
    assert "server died" in by_arm["recall"].error


def test_runner_returning_wrong_cell_is_an_error_record():
    async def runner(row, arm):
        return SessionRecord(task_id="other", arm=arm, success=True)

    records = asyncio.run(run_grid([{"task_id": "t1"}], ("bare",), runner))
    assert records[0].error is not None


def test_duplicate_cells_are_refused():
    async def runner(row, arm):
        return _ok(row, arm)

    with pytest.raises(ValueError, match="unique"):
        asyncio.run(
            run_grid([{"task_id": "t1"}, {"task_id": "t1"}], ("bare",), runner)
        )


def test_duplicate_arms_are_refused():
    async def runner(row, arm):
        return _ok(row, arm)

    with pytest.raises(ValueError, match="arms must be unique"):
        asyncio.run(run_grid([{"task_id": "t1"}], ("bare", "bare"), runner))
