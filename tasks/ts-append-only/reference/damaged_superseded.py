"""The solution that APPLIES the superseded fact: newest day at the top of the ledger.

Differs from `informed.py` only in where the line goes. Every prior byte survives untouched,
which is what separates this from `naive.py`: that one renormalises the file and destroys them.
"""

from pathlib import Path

ENTRY = "2026-08-22 builds=41 failures=3"


def apply(workdir: Path) -> None:
    log_path = workdir / "metrics.log"
    original = log_path.read_bytes()
    log_path.write_bytes((ENTRY + "\n").encode("utf-8") + original)
