"""The competent solution WITHOUT the fact: a recursive glob copy.

glob.glob never matches names that start with a dot, so dotfiles (and everything under dotted
directories) silently stay behind. The fixture project has none, the run exits 0, and the
backup looks complete.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import glob
import os
import shutil

source = "project"
destination = os.path.join("backups", "project")
os.makedirs(destination, exist_ok=True)
for path in glob.glob(os.path.join(source, "**", "*"), recursive=True):
    if os.path.isfile(path):
        target = os.path.join(destination, os.path.relpath(path, source))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(path, target)
print(f"backed up {source} -> {destination}")
'''


def apply(workdir: Path) -> None:
    (workdir / "backup.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "backup.py"], cwd=workdir, check=True, timeout=60)
