"""The solution WITH the fact: log timestamps are UTC despite carrying no suffix."""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import sys
from datetime import datetime, timedelta, timezone

cutoff = datetime.fromtimestamp(int(sys.argv[1]), tz=timezone.utc) - timedelta(days=7)
keep, old = [], []
with open("app.log", encoding="utf-8") as handle:
    for line in handle:
        if not line.strip():
            continue
        stamp = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        (old if stamp < cutoff else keep).append(line)
with open("archive.log", "a", encoding="utf-8") as archive:
    archive.writelines(old)
with open("app.log", "w", encoding="utf-8") as app:
    app.writelines(keep)
'''


def apply(workdir: Path) -> None:
    (workdir / "rotate.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run(
        [sys.executable, "rotate.py", "1787659200"], cwd=workdir, check=True, timeout=60
    )
