"""The solution that APPLIES the superseded fact: skip dotted directories, keep dotfiles.

Differs from `informed.py` only by the dotted-directory exclusion. Root dotfiles are copied, so
this is not the glob failure `naive.py` produces, which loses every dotted thing at once.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import shutil
from pathlib import Path

source = Path("project")
target = Path("backups") / "project"
for path in sorted(source.rglob("*")):
    if not path.is_file():
        continue
    relative = path.relative_to(source)
    if any(part.startswith(".") for part in relative.parts[:-1]):
        continue
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
'''


def apply(workdir: Path) -> None:
    (workdir / "backup.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "backup.py"], cwd=workdir, check=True, timeout=60)
