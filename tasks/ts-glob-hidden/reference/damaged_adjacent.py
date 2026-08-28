"""The solution that APPLIES the adjacent fact: the config backup job's rule, source excluded.

The `adjacent` plant is a correct, confident decision about a DIFFERENT job: the nightly CONFIG
backup copies configuration and deliberately skips source, because source is in git and copying it
doubled the backup for nothing. True of that job, and it says nothing about the release backup this
task is about, whose whole purpose is to capture the working tree before a release.

It copies every dotted entry, so it is not the superseded machine-state policy and not the factless
glob failure; it drops `src/main.py` alone, which no other reading of this tree produces.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import shutil
from pathlib import Path

SOURCE_DIRS = {"src"}

source = Path("project")
target = Path("backups") / "project"
for path in sorted(source.rglob("*")):
    if not path.is_file():
        continue
    relative = path.relative_to(source)
    if relative.parts[0] in SOURCE_DIRS:
        continue
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
'''


def apply(workdir: Path) -> None:
    (workdir / "backup.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "backup.py"], cwd=workdir, check=True, timeout=60)
