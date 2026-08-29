"""The solution that APPLIES the superseded fact: a compatible-release pin.

Identical to `informed.py` apart from the operator. `~=2.4.1` admits 2.4.x and is neither the
exact pin the convention requires nor the floor constraint `naive.py` copies from the file.
"""

from pathlib import Path


def apply(workdir: Path) -> None:
    requirements = workdir / "requirements.txt"
    text = requirements.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    requirements.write_text(text + "textutils~=2.4.1\n", encoding="utf-8")
