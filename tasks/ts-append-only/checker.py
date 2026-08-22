"""Compare the produced metrics.log byte-for-byte against its recorded prior state.

Bytes ARE the convention under test: the ledger is append-only, so the prior content,
inconsistent spacing and all, must survive as a byte-identical prefix, with exactly the one
new entry after it. A normalised rewrite parses identically and is precisely the violation.
"""

from __future__ import annotations

import re
from pathlib import Path

ENTRY = "2026-08-22 builds=41 failures=3"


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    log_path = workdir / "metrics.log"
    if not log_path.is_file():
        return False, "metrics.log is missing from the sandbox"
    produced = log_path.read_bytes()
    original = (oracle_dir / "metrics_before.log").read_bytes()

    if not produced.startswith(original):
        return False, "the prior content is no longer a byte-identical prefix: history was rewritten"
    tail = produced[len(original) :].decode("utf-8", errors="replace")
    tail_lines = [line for line in tail.splitlines() if line.strip()]
    if not tail_lines:
        return False, "nothing was appended for 2026-08-22"
    if len(tail_lines) > 1:
        return False, f"more than one line was appended: {tail_lines}"
    appended = tail_lines[0].strip()
    if not re.fullmatch(r"2026-08-22\s+builds=41\s+failures=3", appended):
        return False, f"appended line is not the requested entry: {appended!r}"
    return True, "history untouched, one entry appended"
