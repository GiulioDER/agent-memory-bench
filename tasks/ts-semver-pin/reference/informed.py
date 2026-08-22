"""The solution WITH the fact: internal packages are pinned exactly."""

from pathlib import Path


def apply(workdir: Path) -> None:
    requirements = workdir / "requirements.txt"
    text = requirements.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    requirements.write_text(text + "textutils==2.4.1\n", encoding="utf-8")
