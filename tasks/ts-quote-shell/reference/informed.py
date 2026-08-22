"""The solution WITH the fact: every path expansion quoted, existing lines included."""

from pathlib import Path

SCRIPT = """\
#!/usr/bin/env bash
set -euo pipefail

TARGET="$1"

mkdir -p "$TARGET/app"
cp app/main.py "$TARGET/app/"
cp -r assets "$TARGET/"
echo "deployed app to $TARGET"
"""


def apply(workdir: Path) -> None:
    (workdir / "deploy.sh").write_text(SCRIPT, encoding="utf-8", newline="\n")
