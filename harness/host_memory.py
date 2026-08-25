"""Refusing to start a session the host does not have the memory to run.

A memory arm's session starts an MCP server, and recall's loads fastembed before it can answer
`initialize`. On a starved host that start fails, and the failure is not loud: Claude Code reports
the server as `failed` with an EMPTY `mcp_server_errors`, the session runs with no memory tools,
the model answers from its own knowledge, and the run records a perfectly ordinary looking result.
`harness/gate.py` catches it and discards the cell, which is correct and also means the run quietly
converts host contention into missing data.

Measured 2026-08-26 during `diagnostic-002` on this 12 GB workstation: free memory was **421 MB**,
and the recall arm wired for its first six sessions and then failed nearly every one after. Two
cells burned all three retry attempts without ever getting a tool. Killing everything the run owned
recovered nothing (471 MB to 422 MB), because the ~2 GB in flight belonged to other work on the
same box, including another session's pytest run. So the run was a victim of contention rather than
its cause, and no amount of retrying was going to win.

The retry in `harness/memory_startup.py` is the right mechanism for a TRANSIENT. It is the wrong
mechanism for a shortage, where it triples the sessions spent on a cell that cannot succeed, and
where the diagnostic probe makes things actively worse by starting yet another server at the moment
memory is scarcest. Hence a precondition rather than a cure: wait for headroom, record the wait,
and let a starved host slow the run down visibly instead of corrupting it silently.

Stdlib only, like the rest of the harness. Returns ``None`` rather than guessing on a platform it
cannot read, and a caller that cannot measure memory must not pretend it checked.
"""

from __future__ import annotations

import ctypes
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _windows_free_mb() -> float | None:
    try:
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return status.ullAvailPhys / (1024 * 1024)
    except (AttributeError, OSError):
        return None


def _linux_free_mb() -> float | None:
    """MemAvailable, not MemFree: the kernel's own estimate of what a new process can get."""

    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return float(line.split()[1]) / 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def free_memory_mb() -> float | None:
    """Physical memory a new process could plausibly get, or None if this host cannot say."""

    if sys.platform.startswith("win"):
        return _windows_free_mb()
    if sys.platform.startswith("linux"):
        return _linux_free_mb()
    return None


@dataclass(frozen=True)
class HeadroomWait:
    """What one precondition check saw, whether or not it had to wait."""

    required_mb: float
    observed_mb: float | None
    waited_s: float
    satisfied: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "required_mb": self.required_mb,
            "observed_mb": None if self.observed_mb is None else round(self.observed_mb, 1),
            "waited_s": round(self.waited_s, 1),
            "satisfied": self.satisfied,
        }


def wait_for_headroom(
    required_mb: float,
    *,
    timeout_s: float = 900.0,
    poll_s: float = 15.0,
    reader: Callable[[], float | None] = free_memory_mb,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> HeadroomWait:
    """Block until the host has `required_mb` free, or until `timeout_s` elapses.

    A host that cannot report its memory is treated as satisfied and says so through
    ``observed_mb=None``, because refusing to run on every unreadable platform would be worse than
    the failure this guards. Timing out is NOT an exception: the caller decides whether to run
    anyway and record the shortfall, or to stop. Both are legitimate and the record shows which.
    """

    if required_mb <= 0:
        raise ValueError("required_mb must be positive")
    started = clock()
    observed = reader()
    if observed is None:
        return HeadroomWait(required_mb, None, 0.0, True)
    while observed < required_mb:
        if clock() - started >= timeout_s:
            return HeadroomWait(required_mb, observed, clock() - started, False)
        sleep(poll_s)
        current = reader()
        if current is None:  # became unreadable mid-wait; do not stall forever on a blind host
            return HeadroomWait(required_mb, None, clock() - started, True)
        observed = current
    return HeadroomWait(required_mb, observed, clock() - started, True)
