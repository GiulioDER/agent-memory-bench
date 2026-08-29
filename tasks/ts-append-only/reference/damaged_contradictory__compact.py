"""The solution that APPLIES THE OTHER SIDE of the contradiction: the entry dated compact, without separators.

Differs from `informed.py` only in how the date is written. History is appended to and never
touched, which is what separates every planted outcome here from `naive.py`: that one renormalises
the whole file, and a rewritten history is the factless failure whatever was appended to it.

This is memo B of the pair, and it exists so the gate exercises BOTH planted entries.
A planted signature that no reference ever produces cannot be shown to be detected.
"""

from pathlib import Path

ENTRY = "20260822 builds=41 failures=3"


def apply(workdir: Path) -> None:
    with open(workdir / "metrics.log", "a", encoding="utf-8", newline="") as handle:
        handle.write(ENTRY + "\n")
