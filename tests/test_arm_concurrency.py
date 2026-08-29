"""Running a cell's arms one at a time, without handing one arm the quiet end of every cell.

`harness/runner.py` starts a cell's arms together on purpose, so no arm systematically runs on a
busier host. That default is not always affordable: four concurrent sessions, each with its own MCP
server holding an embedder, took this 12 GB workstation to an out-of-memory REBOOT on 2026-08-26,
after three earlier runs had already died of memory. A comparison whose host dies is not a
comparison, so `arm_concurrency=1` exists.

It reintroduces the hazard the default guards against, so the order is a seeded per-cell
permutation rather than fixed. A fixed order would give the first arm every cell's quietest instant
and the last arm every cell's busiest, and the harness would then report that as a treatment
effect. Every record carries `arm_order`, `arm_position` and `arm_concurrency`, so the residual
order effect is testable after the fact instead of assumed away.
"""

from __future__ import annotations

import asyncio

import pytest

from harness.runner import arm_order, run_grid
from harness.schema import SessionRecord

ARMS = ("bare", "claude_md", "recall", "oracle_memory")
ROWS = [{"task_id": f"ts-{i}", "seed": s, "user_input": "go"} for i in range(3) for s in range(2)]


def _runner(log, *, overlap=None):
    """A runner that records call order and, optionally, how many ran at once."""

    live = {"now": 0, "peak": 0}

    async def run(row, arm):
        live["now"] += 1
        live["peak"] = max(live["peak"], live["now"])
        log.append((row["task_id"], row["seed"], arm))
        await asyncio.sleep(0)
        live["now"] -= 1
        return SessionRecord(
            task_id=str(row["task_id"]), arm=arm, seed=int(row["seed"]), success=True
        )

    if overlap is not None:
        overlap["live"] = live
    return run


def test_sequential_arms_never_overlap():
    """Mutation: gathering the arms anyway. Peak concurrency goes to 4 and the memory saving,
    which is the entire reason this option exists, silently disappears."""

    log, seen = [], {}
    records = asyncio.run(
        run_grid(ROWS, ARMS, _runner(log, overlap=seen), arm_concurrency=1)
    )
    assert seen["live"]["peak"] == 1, "arms overlapped despite arm_concurrency=1"
    assert len(records) == len(ROWS) * len(ARMS)


def test_all_arms_together_is_still_the_default():
    """Mutation: making sequential the default in run_grid. scripts/pilot.py calls this, and
    pilot-003 and pilot-004 must stay reproducible."""

    log, seen = [], {}
    asyncio.run(run_grid(ROWS, ARMS, _runner(log, overlap=seen)))
    assert seen["live"]["peak"] == len(ARMS)


def test_arm_order_is_permuted_per_cell_not_fixed():
    """Mutation: returning the arms unshuffled. Then the first arm gets every cell's quietest
    instant and the last gets every cell's busiest, and that bias reads as a treatment effect."""

    orders = {arm_order(ARMS, (f"ts-{i}", s), "seed") [0] for i in range(6) for s in range(3)}
    assert len(orders) > 1, "the same arm led every cell; the order is not permuted"


def test_arm_order_is_reproducible_from_its_seed():
    first = arm_order(ARMS, ("ts-1", 0), "run-a")
    assert first == arm_order(ARMS, ("ts-1", 0), "run-a")
    assert set(first) == set(ARMS)


def test_a_different_seed_gives_a_different_schedule():
    same = [arm_order(ARMS, (f"ts-{i}", 0), "run-a") == arm_order(ARMS, (f"ts-{i}", 0), "run-b")
            for i in range(12)]
    assert not all(same), "the seed does not affect the order"


def test_every_record_carries_its_position_and_the_order():
    """Mutation: dropping the annotation. The order effect then cannot be tested at all, which
    turns a measurable limitation into an invisible one."""

    records = asyncio.run(run_grid(ROWS, ARMS, _runner([]), arm_concurrency=1))
    for record in records:
        assert set(record.metadata["arm_order"]) == set(ARMS)
        assert record.metadata["arm_concurrency"] == 1
        assert record.metadata["arm_order"][record.metadata["arm_position"]] == record.arm


def test_every_cell_still_runs_every_arm_exactly_once():
    log = []
    asyncio.run(run_grid(ROWS, ARMS, _runner(log), arm_concurrency=1))
    assert len(log) == len(ROWS) * len(ARMS)
    assert len(set(log)) == len(log)


def test_a_nonsense_arm_concurrency_is_refused():
    with pytest.raises(ValueError, match="arm_concurrency must be at least one"):
        asyncio.run(run_grid(ROWS, ARMS, _runner([]), arm_concurrency=0))


def test_bounded_concurrency_between_the_two_extremes():
    seen = {}
    asyncio.run(run_grid(ROWS, ARMS, _runner([], overlap=seen), arm_concurrency=2))
    assert seen["live"]["peak"] <= 2
