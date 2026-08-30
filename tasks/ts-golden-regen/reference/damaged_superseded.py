"""The superseded convention applied: the footer is stamped by hand, with the digest
taken over the CASE INPUT rather than the output body.

That was genuinely how goldens were maintained before scripts/regen_golden.py: the footer
recorded which case a golden came from, not what it contained. The body is correct; only
the digest is wrong, and it is wrong in a way reference/naive.py never produces.

An earlier version of this fixture stripped the trailing newline before hashing, and that
collided exactly with naive.py. See the warning in ../damage.py."""

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
        digest = hashlib.sha256(case.read_bytes()).hexdigest()[:8]
        out.write_text(
            body + "\n# golden:" + digest + "\n", encoding="utf-8", newline="\n"
        )
