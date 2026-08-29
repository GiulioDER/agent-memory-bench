"""The solution that APPLIES the adjacent fact: the metrics exporter's comma-joined pair syntax.

The `adjacent` plant is a correct, confident decision about a DIFFERENT ledger: the metrics
exporter writes its pairs comma-joined on one line, because the collector that scrapes it splits on
commas and treats a space as the end of the record. True of that ledger, and it says nothing about
this one, which a reporting job reads nightly.

History is appended to and never touched, which is what separates this from `naive.py`: that one
renormalises the whole file. The field ORDER is correct here, so it is not the superseded reading
either; only the separator between the pairs differs.
"""

from pathlib import Path

ENTRY = "2026-08-22 builds=41,failures=3"


def apply(workdir: Path) -> None:
    with open(workdir / "metrics.log", "a", encoding="utf-8", newline="") as handle:
        handle.write(ENTRY + "\n")
