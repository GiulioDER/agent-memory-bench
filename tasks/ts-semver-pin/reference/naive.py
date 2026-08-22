"""The competent solution WITHOUT the fact: follow the file's own style, which is >= ranges.

Every existing entry is a floor constraint, so the consistent edit is textutils>=2.4.1. It
resolves, installs and imports; the breakage arrives with the next internal release, which
the sandbox will never see.
"""

from pathlib import Path


def apply(workdir: Path) -> None:
    requirements = workdir / "requirements.txt"
    text = requirements.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    requirements.write_text(text + "textutils>=2.4.1\n", encoding="utf-8")
