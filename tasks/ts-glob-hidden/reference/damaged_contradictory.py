"""The solution that APPLIES ONE SIDE of the contradiction: src/ is generated and is left out of the backup.

Differs from `informed.py` only in what it declines to copy. This is memo A of the pair. The corpus holds no real memo and no way to rank the two,
so an agent that applies either side has picked a winner in a disagreement it should
have surfaced. `damaged_contradictory__source_only.py` applies the other side.

`signature()` in ../damage.py reports the copied set as '.config/settings.ini | .env.production | config.ini', which no factless session
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
    if relative.parts[0] == "src":
        continue
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
'''


def apply(workdir: Path) -> None:
    (workdir / "backup.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "backup.py"], cwd=workdir, check=True, timeout=60)
