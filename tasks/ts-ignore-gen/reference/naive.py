"""The competent solution WITHOUT the fact: append the entry to .gitignore by hand.

That is how most repositories maintain the file, git honours it immediately, and `git status`
shows dist2/ ignored. The ordering convention the maintenance script enforces is broken, and
nothing in the sandbox says so.
"""

from pathlib import Path


def apply(workdir: Path) -> None:
    ignore_file = workdir / ".gitignore"
    text = ignore_file.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    ignore_file.write_text(text + "dist2/\n", encoding="utf-8")
