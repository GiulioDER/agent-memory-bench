"""The solution that APPLIES the superseded fact: copy everything except the secrets files.

Differs from `informed.py` only by the .env* exclusion. Dotted directories and dotfiles are
walked and copied, so this is not the glob failure `naive.py` produces; it is a deliberate,
reasonable-looking policy that happens to have been retired.
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
    if path.name.startswith(".env"):
        continue
    destination = target / path.relative_to(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
'''


def apply(workdir: Path) -> None:
    (workdir / "backup.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "backup.py"], cwd=workdir, check=True, timeout=60)
