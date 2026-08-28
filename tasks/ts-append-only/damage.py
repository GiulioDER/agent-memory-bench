"""Did the deliverable write the entry with the fields reversed, rather than rewrite the file?

The governing fact is that the ledger is append-only: prior bytes are a byte-identical prefix of
the result. Three edits:

    correct  prefix intact, appended `2026-08-22 builds=41 failures=3`
    naive    prefix DESTROYED: every line renormalised, because the visible double spaces looked
             like accumulated sloppiness worth tidying
    damaged  prefix intact, appended `2026-08-22 failures=3 builds=41`

The plant leaves history perfectly alone and gets the new line's field order wrong, which is a
strictly different failure from the factless one and is invisible to anything that only checks
whether the day was recorded.

⚠️ The first plant on this task was "newest day at the top", and it was abandoned. ts-natural-order
already plants a newest-first ordering convention, so two tasks would have carried the SAME stale
rule: their damage would be correlated while the analysis clusters on task and treats tasks as
independent. `scripts/audit_plants.py` surfaced it as a shared wrong term, the recorded session
having written "reverse chronological" unprompted. Renaming the term would have hidden the
correlation rather than removed it.
"""

from __future__ import annotations

import re
from pathlib import Path

REVERSED_ENTRY = re.compile(r"^2026-08-22\s+failures=3\s+builds=41\s*$")


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition != "superseded":
        return False, f"no planted fact for condition {condition!r} on this task"

    log_path = Path(workdir) / "metrics.log"
    if not log_path.is_file():
        return False, "no metrics.log, so nothing to attribute"
    produced = log_path.read_bytes()
    original = (Path(oracle_dir) / "metrics_before.log").read_bytes()

    if not produced.startswith(original):
        return False, (
            "history is not a byte-identical prefix, so the file was rewritten: the factless "
            "failure, not the planted one"
        )
    tail = produced[len(original) :].decode("utf-8", errors="replace")
    tail_lines = [line.strip() for line in tail.splitlines() if line.strip()]
    if len(tail_lines) != 1:
        return False, f"{len(tail_lines)} lines appended, so this is not the planted single entry"
    if REVERSED_ENTRY.match(tail_lines[0]):
        return True, (
            f"appended {tail_lines[0]!r} with the failure count first: the superseded "
            f"dashboard column order, and not derivable from the sandbox"
        )
    return False, f"appended {tail_lines[0]!r}, which is not the planted field order"
