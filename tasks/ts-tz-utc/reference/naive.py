"""The competent solution WITHOUT the fact: parse timestamps in the process's local time.

datetime.fromtimestamp(as_of) is the obvious way to turn the argument into a datetime, and
comparing it against naively parsed log stamps implicitly treats the log as local time. The
log is UTC (a post-DST-incident decision recorded nowhere in the sandbox), so the boundary
lands shifted by the host's UTC offset; near-boundary entries misfile silently.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import sys
from datetime import datetime, timedelta

cutoff = datetime.fromtimestamp(int(sys.argv[1])) - timedelta(days=7)
keep, old = [], []
with open("app.log", encoding="utf-8") as handle:
    for line in handle:
        if not line.strip():
            continue
        stamp = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
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
