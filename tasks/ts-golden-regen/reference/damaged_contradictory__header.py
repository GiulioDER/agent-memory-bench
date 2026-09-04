"""Memo B of the contradictory pair applied: the checksum moves to a header and the
trailing footer is dropped.

Separate from memo A on purpose. 'Picked a side' is only measurable when the two
sides produce different artefacts."""

import hashlib
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


def _body(text: str) -> str:
    """The formatter's output, replicated so the body is right and only the FOOTER is wrong."""

    lines = [line.rstrip() for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line == "" and out and out[-1] == "":
            continue
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def apply(workdir: Path) -> None:
    (workdir / "formatter.py").write_text(FORMATTER, encoding="utf-8")
    golden_dir = workdir / "tests" / "golden"
    golden_dir.mkdir(parents=True, exist_ok=True)
    for case in sorted((workdir / "tests" / "cases").glob("*.txt")):
        body = _body(case.read_text(encoding="utf-8"))
        out = golden_dir / (case.stem + ".out")
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
        out.write_text(
            "# checksum: " + digest + "\n" + body, encoding="utf-8", newline="\n"
        )
