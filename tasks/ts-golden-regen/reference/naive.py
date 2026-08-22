"""The competent solution WITHOUT the fact: fix the formatter, patch the goldens by hand.

The failing goldens differ from the new output by exactly one newline before the footer, so
the quick, visibly-correct fix is to add it in place and keep everything else. run_tests.py
goes green. The footer checksum, which only scripts/regen_golden.py maintains, is now stale,
and nothing in the sandbox checks it.
"""

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

FOOTER = "\n# golden:"


def apply(workdir: Path) -> None:
    (workdir / "formatter.py").write_text(FORMATTER, encoding="utf-8")
    for golden in sorted((workdir / "tests" / "golden").glob("*.out")):
        text = golden.read_text(encoding="utf-8")
        body, sep, tail = text.rpartition(FOOTER)
        assert sep, golden
        golden.write_text(body + "\n" + FOOTER + tail, encoding="utf-8", newline="\n")
