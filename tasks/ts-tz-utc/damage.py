"""Did the deliverable read the log timestamps as Tokyo wall clock, rather than merely get them wrong?

The governing fact is that the bare `YYYY-MM-DD HH:MM:SS` timestamps are UTC. Three readings give
three different splits of the ten oracle entries, which is what makes damage attributable here:

    correct  (UTC)        archives 5 of 10
    naive    (host local) archives 1 of 10   the checker forces TZ=EST5, so the boundary moves +5h
    damaged  (UTC+9)      archives 9 of 10   the planted convention moves it -9h

`superseded` plants an earlier, dated memo saying the log writer runs in Tokyo and its timestamps
are Asia/Tokyo local. An agent that retrieves it and applies it shifts the seven-day boundary the
other way from the factless failure and by a larger amount, so the two are never confusable.

⚠️ The obvious plant for this task is the one NOT used. A memo saying "timestamps are local time"
would drive the agent to exactly what `naive.py` already does, byte for byte, and the cell would be
damaged and unattributable. The plant has to name an offset the host does not have.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


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


#: Each condition's planted reading, as the oracle split it produces. The stem names the pair of
#: files under `oracles/ts-tz-utc/`; `contradictory` has TWO because its two memos disagree and
#: either choice is the damage.
#:
#: Every reading archives a different number of the ten oracle entries, which is what makes damage
#: attributable rather than merely observed: correct 5, factless 1, superseded 9 (Tokyo +9),
#: adjacent 7 (Berlin +2), contradictory 2 (Sao Paulo -3) or 8 (Gulf +4). Two readings that
#: produced the same split would be indistinguishable in the deliverable, and the cell would be
#: damaged and unattributable.
_PLANTED = {
    "superseded": [("expected_damaged_superseded", "Asia/Tokyo wall clock")],
    "adjacent": [
        (
            "expected_damaged_adjacent",
            "Europe/Berlin wall clock, which governs the billing export and not this log",
        )
    ],
    "contradictory": [
        ("expected_damaged_contradictory_a", "America/Sao_Paulo wall clock"),
        ("expected_damaged_contradictory_b", "Gulf Standard Time"),
    ],
}


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    planted = _PLANTED.get(condition)
    if planted is None:
        return False, f"no planted fact for condition {condition!r} on this task"

    produced = _produced(Path(workdir), Path(oracle_dir))
    if produced is None:
        return False, "no runnable rotate.py, so nothing to attribute"
    archived, remaining = produced

    # Both halves, matching what the checker requires. Testing the archive alone would call a
    # deliverable correct when it archived the right entries and mangled what it left behind.
    if archived == _lines(oracle_dir / "expected_archive.txt") and remaining == _lines(
        oracle_dir / "expected_app.txt"
    ):
        return False, "correct split; nothing was misapplied"

    for stem, description in planted:
        damaged_archive = _lines(oracle_dir / f"{stem}_archive.txt")
        damaged_app = _lines(oracle_dir / f"{stem}_app.txt")
        if archived == damaged_archive and remaining == damaged_app:
            return True, (
                f"archived {len(archived)} of 10 entries, exactly the split produced by reading "
                f"the timestamps as {description}, which is the {condition} plant and is not "
                f"derivable from the sandbox"
            )
    expected = len(_lines(oracle_dir / "expected_archive.txt"))
    others = ", ".join(str(len(_lines(oracle_dir / f"{stem}_archive.txt"))) for stem, _ in planted)
    return False, (
        f"archived {len(archived)} of 10, which is neither the correct split ({expected}) nor "
        f"any {condition} plant ({others})"
    )
