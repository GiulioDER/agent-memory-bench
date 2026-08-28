"""The solution that APPLIES the adjacent fact: timestamps read as Europe/Berlin wall clock.

The `adjacent` plant is a correct, confident decision about a DIFFERENT subsystem: the billing
export's own stamps are Europe/Berlin. It is true where it was written and says nothing about
app.log, so an agent that retrieves it and applies it here has carried a rule across a boundary the
memo never crossed.

Identical to `informed.py` apart from the two-hour offset. That single difference archives 7 of the
ten oracle entries, against 5 correct, 1 factless and 9 superseded, so all four readings are
separable and the failure is attributable to this plant rather than to ordinary error.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import sys
from datetime import datetime, timedelta, timezone

BERLIN = timezone(timedelta(hours=2))

cutoff = datetime.fromtimestamp(int(sys.argv[1]), tz=timezone.utc) - timedelta(days=7)
keep, old = [], []
with open("app.log", encoding="utf-8") as handle:
    for line in handle:
        if not line.strip():
            continue
        stamp = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=BERLIN)
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
