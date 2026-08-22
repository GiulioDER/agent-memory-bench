"""The solution WITH the fact: append the entry and touch nothing above it."""

from pathlib import Path

ENTRY = "2026-08-22 builds=41 failures=3"


def apply(workdir: Path) -> None:
    with open(workdir / "metrics.log", "a", encoding="utf-8", newline="") as handle:
        handle.write(ENTRY + "\n")
