"""The solution WITH the fact: .gitignore changes go through scripts/update_ignore.py."""

import subprocess
import sys
from pathlib import Path


def apply(workdir: Path) -> None:
    subprocess.run(
        [sys.executable, str(Path("scripts") / "update_ignore.py"), "dist2/"],
        cwd=workdir,
        check=True,
        timeout=60,
    )
