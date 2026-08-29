"""The solution that APPLIES the superseded fact: the failure count leads the entry.

Differs from `informed.py` only in the order of the two fields. History is appended to and never
touched, which is what separates this from `naive.py`: that one renormalises the whole file.
"""

from pathlib import Path

ENTRY = "2026-08-22 failures=3 builds=41"


def apply(workdir: Path) -> None:
    with open(workdir / "metrics.log", "a", encoding="utf-8", newline="") as handle:
        handle.write(ENTRY + "\n")
