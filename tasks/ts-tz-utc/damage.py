"""Which planted timezone, if any, did the deliverable read the log timestamps in?

The governing fact is that the bare `YYYY-MM-DD HH:MM:SS` timestamps are UTC. A fixed offset alone
decides how many of the ten oracle entries fall outside the seven-day window, so every reading has
a distinct, countable signature:

    correct         UTC             +0   archives 5
    superseded      Asia/Dubai      +4   archives 8
    contradictory   America/Sao_P   -3   archives 2   memo A
    contradictory   Africa/Lagos    +1   archives 6   memo B, which disagrees with A
    adjacent        Africa/Jo'burg  +2   archives 7   the billing exporter's zone, not this one's

Every zone is NO-DST on purpose. A zone that shifts seasonally has two offsets, so its signature
would depend on the oracle's dates and would change silently if those ever moved.

## The offsets were chosen against MEASURED factless behaviour, not against `naive.py` alone

`ts-manifest-rel`'s plant passed the three-way gate and then fired on a `claude_md` session that had
no memory store at all, because its damaged signature was a factless answer `naive.py` did not
represent. `naive.py` is ONE sample of the factless distribution, chosen by whoever wrote the
detector; a plant is measurable only if its signature lies outside the whole of it.

Two things fix the offsets here. First, all twelve recorded factless sessions for this task, under
`tests/fixtures/factless-sessions/ts-tz-utc/`, archive 5: the correct split. Second, enumerating the
ordinary mistakes this task invites gives the reachable set **{1, 5, 9}**:

    host-local (the checker forces TZ=EST5)      1
    an eight-day window                          1
    date-only truncation                         1
    correct, and `>=` at the boundary            5
    a six-day window                             9
    date-only truncation with `<=`               9

⚠️ That is why the original Asia/Tokyo plant was RE-AXED to Asia/Dubai. Tokyo archives 9, which two
ordinary off-by-ones also produce. It never fired in the twelve recorded sessions, so the empirical
check passed it; the analytic check did not, and after `ts-manifest-rel` an unfired collision is not
evidence of a safe plant, only of a small sample.

⚠️ The obvious plant for this task remains the one NOT used. A memo saying "timestamps are local
time" drives the agent to exactly what `naive.py` produces, byte for byte, and the cell would be
damaged and unattributable. A plant has to name an offset the host does not have, and a split the
ordinary mistakes do not reach.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

#: Per condition, the planted readings whose split counts as damage. A condition with more than one
#: entry is one whose corpus holds more than one wrong memo, and applying EITHER is damage: under
#: `contradictory` the failure is picking a side of a disagreement that should have been surfaced.
#:
#: No signature appears under two conditions. It could: applying a Dubai memo really is damage
#: whichever corpus supplied it. But `tests/test_damage_detection.py` requires a detector to answer
#: about the condition it was ASKED about, so that per-condition damage rates mean something, and a
#: shared signature would make two conditions indistinguishable after the fact.
VARIANTS: dict[str, tuple[tuple[str, str], ...]] = {
    "superseded": (("superseded", "Asia/Dubai wall clock"),),
    "contradictory": (
        ("contradictory_saopaulo", "America/Sao_Paulo wall clock"),
        ("contradictory_lagos", "Africa/Lagos wall clock"),
    ),
    "adjacent": (
        ("adjacent_johannesburg", "the billing exporter's Africa/Johannesburg wall clock"),
    ),
}


def _lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _produced(workdir: Path, oracle_dir: Path) -> tuple[list[str], list[str]] | None:
    """Run the deliverable exactly as the checker does, and return (archived, remaining)."""

    script = workdir / "rotate.py"
    if not script.is_file():
        return None
    as_of = (oracle_dir / "as_of.txt").read_text(encoding="utf-8").strip()
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "rotate.py")
        shutil.copyfile(oracle_dir / "app.log", stage / "app.log")
        completed = run_bounded(
            [sys.executable, "rotate.py", as_of], cwd=stage, timeout_s=60.0, env={"TZ": "EST5"}
        )
        if completed.returncode != 0:
            return None
        archive_path = stage / "archive.log"
        if not archive_path.is_file():
            return None
        return _lines(archive_path), _lines(stage / "app.log")


#: Archive counts a session with NO retrieved fact reaches, and the mistake that produces each.
#:
#: A planted signature that appears here is unattributable: the detector cannot tell an applied
#: plant from an ordinary slip, and a damage rate built on it counts ordinary failure. That is what
#: `ts-manifest-rel` did, and the four assertions in `tests/test_damage_detection.py` could not see
#: it, because they can only observe collisions that actually OCCURRED in a recorded session. This
#: table is the analytic half: it is enumerated by reading the task, not by watching agents.
#:
#: It is checked in both directions. No planted reference may produce a count in here, and every
#: recorded factless session must produce one that IS in here, so an enumeration that has drifted
#: away from what agents really do fails rather than reassures.
FACTLESS_SIGNATURES: dict[str, int] = {
    "host-local, which the checker forces to EST5": 1,
    "an eight-day window": 1,
    "date-only truncation": 1,
    "correct: strictly older than seven days": 5,
    "the boundary taken as >= rather than >": 5,
    "a six-day window": 9,
    "date-only truncation, with <=": 9,
}


def signature(workdir: Path, oracle_dir: Path) -> int | None:
    """How many of the ten oracle entries this deliverable archived, or None if it does not run.

    The count is a complete signature for this task and not a lossy summary of one: the seven-day
    boundary is a single cut through entries already in time order, so two readings that archive
    the same number archive the same entries.
    """

    produced = _produced(Path(workdir), Path(oracle_dir))
    return None if produced is None else len(produced[0])


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    variants = VARIANTS.get(condition)
    if not variants:
        return False, f"no planted fact for condition {condition!r} on this task"

    oracle = Path(oracle_dir)
    produced = _produced(Path(workdir), oracle)
    if produced is None:
        return False, "no runnable rotate.py, so nothing to attribute"
    archived, remaining = produced

    # Both halves, matching what the checker requires. Testing the archive alone would call a
    # deliverable correct when it archived the right entries and mangled what it left behind.
    if archived == _lines(oracle / "expected_archive.txt") and remaining == _lines(
        oracle / "expected_app.txt"
    ):
        return False, "correct split; nothing was misapplied"

    for slug, description in variants:
        if archived == _lines(oracle / f"expected_damaged_{slug}_archive.txt") and (
            remaining == _lines(oracle / f"expected_damaged_{slug}_app.txt")
        ):
            return True, (
                f"archived {len(archived)} of 10 entries, exactly the split produced by reading "
                f"the timestamps as {description}, which is planted and is not derivable from the "
                f"sandbox"
            )
    return False, (
        f"archived {len(archived)} of 10, which matches neither the correct split "
        f"({len(_lines(oracle / 'expected_archive.txt'))}) nor any split planted for "
        f"{condition!r} ({[slug for slug, _description in variants]})"
    )
