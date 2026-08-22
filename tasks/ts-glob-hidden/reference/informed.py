"""The solution WITH the fact: copy the tree wholesale, dotfiles included."""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import shutil
from pathlib import Path

source = Path("project")
destination = Path("backups") / "project"
shutil.copytree(source, destination, dirs_exist_ok=True)
print(f"backed up {source} -> {destination}")
'''


def apply(workdir: Path) -> None:
    (workdir / "backup.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "backup.py"], cwd=workdir, check=True, timeout=60)
