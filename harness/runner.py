"""Concurrent grid execution: N arms per (task, seed) cell, cells one at a time.

Generalised from the ancestor's ``run_paired``. The properties that carry over:

- All arms of one cell start together, so no arm systematically runs on a quieter host.
- ``block_concurrency`` defaults to one cell at a time, because host contention is an
  untracked benchmark variable.
- A runner exception becomes an error record, never a lost row: the analyser and the gate
  decide what an error means, not the scheduler.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from typing import Any

from .schema import SessionRecord

Runner = Callable[
    [Mapping[str, Any], str], Awaitable[SessionRecord | Mapping[str, Any]]
]


def _error_record(row: Mapping[str, Any], arm: str, error: BaseException) -> SessionRecord:
    return SessionRecord(
        task_id=str(row["task_id"]),
        arm=arm,
        seed=int(row.get("seed", 0)),
        success=False,
        user_input=str(row.get("user_input", "")),
        error=f"{type(error).__name__}: {error}",
    )


async def _run_one(row: Mapping[str, Any], arm: str, runner: Runner) -> SessionRecord:
    try:
        result = await runner(row, arm)
        if isinstance(result, SessionRecord):
            record = result
        else:
            record_data = dict(result)
            record_data["task_id"] = row["task_id"]
            record_data["arm"] = arm
            record_data.setdefault("seed", row.get("seed", 0))
            record = SessionRecord.from_mapping(record_data)
        if (
            record.task_id != str(row["task_id"])
            or record.arm != arm
            or record.seed != int(row.get("seed", 0))
        ):
            raise ValueError("runner returned a record for a different cell or arm")
        return record
    except Exception as error:  # noqa: BLE001 - any runner failure must become an error
        # record rather than a lost row; the gate decides what an error means.
        return _error_record(row, arm, error)


async def run_grid(
    rows: Iterable[Mapping[str, Any]],
    arms: Sequence[str],
    runner: Runner,
    *,
    block_concurrency: int = 1,
) -> list[SessionRecord]:
    """Run every arm for each (task, seed) row, starting one cell's arms together.

    ``rows`` must each carry a nonempty ``task_id`` and may carry a ``seed`` (default 0);
    the (task_id, seed) cells must be unique within one run. ``arms`` is the ordered arm
    roster for this run and must not repeat.
    """

    if block_concurrency < 1:
        raise ValueError("block_concurrency must be at least one")
    arm_list = list(arms)
    if not arm_list:
        raise ValueError("arms must not be empty")
    if len(arm_list) != len(set(arm_list)):
        raise ValueError("arms must be unique within one run")

    materialized = [dict(row) for row in rows]
    cells = [(str(row.get("task_id", "")), int(row.get("seed", 0))) for row in materialized]
    if any(not task_id for task_id, _ in cells):
        raise ValueError("every row must contain a nonempty task_id")
    if len(cells) != len(set(cells)):
        raise ValueError("(task_id, seed) cells must be unique within one grid run")

    semaphore = asyncio.Semaphore(block_concurrency)

    async def run_cell(row: Mapping[str, Any]) -> list[SessionRecord]:
        async with semaphore:
            return list(
                await asyncio.gather(*(_run_one(row, arm, runner) for arm in arm_list))
            )

    blocks = await asyncio.gather(*(run_cell(row) for row in materialized))
    return [record for block in blocks for record in block]
