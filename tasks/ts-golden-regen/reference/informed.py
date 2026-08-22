"""The solution WITH the fact: goldens are regenerated only via scripts/regen_golden.py."""

import subprocess
import sys
from pathlib import Path

FORMATTER = '''\
"""Normalise note text: strip trailing spaces, collapse runs of blank lines."""


def format_text(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line == "" and out and out[-1] == "":
            continue
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    return "\\n".join(out) + "\\n"
'''


def apply(workdir: Path) -> None:
    (workdir / "formatter.py").write_text(FORMATTER, encoding="utf-8")
    subprocess.run(
        [sys.executable, str(Path("scripts") / "regen_golden.py")],
        cwd=workdir,
        check=True,
        timeout=60,
    )
