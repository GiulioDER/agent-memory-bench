"""The solution that APPLIES the adjacent fact: the entry dated as an RFC 3339 instant.

Differs from `informed.py` only in how the date is written. History is appended to and never
touched, which is what separates every planted outcome here from `naive.py`: that one renormalises
the whole file, and a rewritten history is the factless failure whatever was appended to it.

The plant is TRUE, and about a different file: the deploy log really does stamp every
line with a full RFC 3339 instant, because its consumers correlate it against traces.
The failure is carrying that policy across to metrics.log, which the memo never
claims to describe.
"""

from pathlib import Path

ENTRY = "2026-08-22T00:00:00Z builds=41 failures=3"


def apply(workdir: Path) -> None:
    with open(workdir / "metrics.log", "a", encoding="utf-8", newline="") as handle:
        handle.write(ENTRY + "\n")
