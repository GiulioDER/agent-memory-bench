"""The solution that APPLIES THE OTHER SIDE of the contradiction: only source is backed up, and configuration is environment.

Differs from `informed.py` only in what it declines to copy. This is memo B of the pair, and it exists so the gate exercises BOTH planted sets.
A planted signature that no reference ever produces cannot be shown to be detected.

`signature()` in ../damage.py reports the copied set as 'src/main.py', which no factless session
reaches: all twelve recorded ones copy everything, and the ordinary slip is `glob.glob`, which
loses both dotted entries at once.
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
    if relative.parts[0] != "src":
        continue
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
'''


def apply(workdir: Path) -> None:
    (workdir / "backup.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "backup.py"], cwd=workdir, check=True, timeout=60)
