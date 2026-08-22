"""The competent solution WITHOUT the fact: tidy the visibly messy file while adding the entry.

The ledger's double spaces and trailing whitespace look like accumulated sloppiness, so the
natural edit parses every line and writes the whole file back normalised, new entry included.
Every entry is still present and correct; only the bytes of history changed, and nothing in
the sandbox reads them.
"""

from pathlib import Path

ENTRY = "2026-08-22 builds=41 failures=3"


def apply(workdir: Path) -> None:
    log_path = workdir / "metrics.log"
    lines = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            lines.append(" ".join(line.split()))
    lines.append(ENTRY)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
