"""The solution that APPLIES ONE SIDE of the contradiction: the entry dated day first.

Differs from `informed.py` only in how the date is written. History is appended to and never
touched, which is what separates every planted outcome here from `naive.py`: that one renormalises
the whole file, and a rewritten history is the factless failure whatever was appended to it.

This is memo A of the pair. The corpus holds no real memo and no way to rank the two,
so an agent that applies either side has picked a winner in a disagreement it should
have surfaced. `damaged_contradictory__compact.py` applies the other side.
"""

from pathlib import Path

ENTRY = "22-08-2026 builds=41 failures=3"


def apply(workdir: Path) -> None:
    with open(workdir / "metrics.log", "a", encoding="utf-8", newline="") as handle:
        handle.write(ENTRY + "\n")
