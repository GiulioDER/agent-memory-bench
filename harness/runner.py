"""Concurrent grid execution: N arms per (task, seed) cell, cells one at a time.

Generalised from the ancestor's ``run_paired``. The properties that carry over:

- All arms of one cell start together BY DEFAULT, so no arm systematically runs on a
  quieter host.
- ``block_concurrency`` defaults to one cell at a time, because host contention is an
  untracked benchmark variable.

``arm_concurrency`` exists because that default is not always affordable. Four concurrent
sessions, each with its own MCP server holding an embedder, took a 12 GB workstation to an
out-of-memory reboot; the run cannot be comparable if the host dies. Setting it to 1 runs a
cell's arms one after another and cuts peak memory to roughly a quarter.

⚠️ **That reintroduces exactly the hazard the first bullet guards against**, so it is mitigated
rather than accepted: the arm order is a per-cell permutation from a seeded RNG, so a drifting
host cannot favour one arm systematically, and every record carries ``arm_order``,
``arm_position`` and ``arm_concurrency`` so an order effect is testable after the fact rather
than assumed absent. The residual limitation is real and belongs in any report: within a cell
the arms no longer see an identical instant, only an unbiased sample of instants.
- A runner exception becomes an error record, never a lost row: the analyser and the gate
  decide what an error means, not the scheduler.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import replace
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


def arm_order(arms: Sequence[str], cell: tuple[str, int], seed: str) -> list[str]:
    """A per-cell permutation of the arms, reproducible from ``(seed, task, seed_index)``.

    Only used when arms are NOT started together. A fixed order would hand the first arm every
    cell's quietest instant and the last arm every cell's busiest, which is a treatment effect
    the harness would then report as a result. A seeded permutation makes that noise instead of
    bias, and being seeded it replays identically.
    """

    rng = random.Random(f"{seed}|{cell[0]}|{cell[1]}")
    shuffled = list(arms)
    rng.shuffle(shuffled)
    return shuffled


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
    arm_concurrency: int | None = None,
    order_seed: str = "agent-memory-bench",
) -> list[SessionRecord]:
    """Run every arm for each (task, seed) row, starting one cell's arms together.

    ``rows`` must each carry a nonempty ``task_id`` and may carry a ``seed`` (default 0);
    the (task_id, seed) cells must be unique within one run. ``arms`` is the ordered arm
    roster for this run and must not repeat.
    """

    if block_concurrency < 1:
        raise ValueError("block_concurrency must be at least one")
    if arm_concurrency is not None and arm_concurrency < 1:
        raise ValueError("arm_concurrency must be at least one, or None for all arms at once")
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
            cell = (str(row.get("task_id", "")), int(row.get("seed", 0)))
            order = arm_order(arm_list, cell, order_seed) if arm_concurrency else list(arm_list)
            if arm_concurrency == 1:
                records = [await _run_one(row, arm, runner) for arm in order]
            elif arm_concurrency:
                gate = asyncio.Semaphore(arm_concurrency)

                async def bounded(arm: str) -> SessionRecord:
                    async with gate:
                        return await _run_one(row, arm, runner)

                records = list(await asyncio.gather(*(bounded(arm) for arm in order)))
            else:
                records = list(await asyncio.gather(*(_run_one(row, arm, runner) for arm in order)))
            return [
                replace(
                    record,
                    metadata={
                        **record.metadata,
                        "arm_order": list(order),
                        "arm_position": position,
                        "arm_concurrency": arm_concurrency,
                    },
                )
                for position, record in enumerate(records)
            ]

    blocks = await asyncio.gather(*(run_cell(row) for row in materialized))
    return [record for block in blocks for record in block]
