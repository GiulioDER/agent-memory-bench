"""Waiting for memory the host does not have, instead of spending sessions it cannot run.

diagnostic-002 measured this the expensive way on 2026-08-26. Free memory was 421 MB of 12,279 on
this workstation, the recall arm wired for its first six sessions and then failed nearly every one
after, and two cells burned all three retry attempts without ever seeing a tool. Killing everything
the run owned recovered nothing (471 MB to 422 MB): the ~2 GB in flight belonged to other work on
the same box. The run was a victim of contention, and retrying harder could not win.
"""

from __future__ import annotations

import pytest

from harness.host_memory import HeadroomWait, free_memory_mb, wait_for_headroom


class _Clock:
    """A clock and a sleep that agree with each other, so a wait can be tested without one."""

    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_this_host_can_report_its_free_memory():
    """Windows and Linux are the platforms this benchmark runs on; if the reader breaks there,
    every headroom check silently becomes a no-op."""

    value = free_memory_mb()
    assert value is None or value > 0


def test_a_host_with_room_does_not_wait():
    clock = _Clock()
    result = wait_for_headroom(
        1000, reader=lambda: 4000.0, sleep=clock.sleep, clock=clock.time
    )
    assert result.satisfied and result.waited_s == 0.0


def test_a_starved_host_waits_until_memory_frees_up():
    """Mutation: checking once and returning. The run then proceeds into the shortage and converts
    contention into discarded cells, which is exactly what diagnostic-002 did."""

    clock = _Clock()
    readings = iter([400.0, 500.0, 900.0, 2500.0])
    result = wait_for_headroom(
        1200, poll_s=15.0, reader=lambda: next(readings), sleep=clock.sleep, clock=clock.time
    )
    assert result.satisfied
    assert result.waited_s == pytest.approx(45.0)
    assert result.observed_mb == 2500.0


def test_a_wait_that_times_out_reports_the_shortfall_rather_than_raising():
    """Timing out is a decision for the caller, not an exception. The run may legitimately proceed
    and record that it did, and the artifact has to show which happened."""

    clock = _Clock()
    result = wait_for_headroom(
        1200, timeout_s=60.0, poll_s=20.0, reader=lambda: 300.0,
        sleep=clock.sleep, clock=clock.time,
    )
    assert not result.satisfied
    assert result.observed_mb == 300.0
    assert result.waited_s >= 60.0


def test_a_host_that_cannot_report_memory_is_not_blocked():
    """Mutation: treating an unreadable host as starved. Every run on an unsupported platform
    would then stall for the full timeout and then run anyway, which is pure delay."""

    result = wait_for_headroom(1200, reader=lambda: None)
    assert result.satisfied and result.observed_mb is None and result.waited_s == 0.0


def test_a_host_that_goes_blind_mid_wait_does_not_stall_forever():
    clock = _Clock()
    readings = iter([400.0, None])
    result = wait_for_headroom(
        1200, poll_s=10.0, reader=lambda: next(readings), sleep=clock.sleep, clock=clock.time
    )
    assert result.satisfied and result.observed_mb is None


def test_a_nonsense_requirement_is_refused():
    with pytest.raises(ValueError, match="must be positive"):
        wait_for_headroom(0)


def test_the_record_is_serialisable_and_rounds():
    payload = HeadroomWait(1200.0, 421.456, 12.345, False).to_dict()
    assert payload == {
        "required_mb": 1200.0,
        "observed_mb": 421.5,
        "waited_s": 12.3,
        "satisfied": False,
    }
