"""The solution that APPLIES the superseded fact: timestamps read as Asia/Dubai wall clock.

Identical to `informed.py` apart from the four-hour offset used when interpreting each stamp.
The plant says the writer box runs in Dubai, so a consumer must treat the bare stamps
as Gulf Standard Time. Dubai does not observe DST, so the offset is one number all year.

Split of the ten oracle entries: 8 archived, where the correct answer archives 5 and the
factless mistakes this task invites archive 1 or 9. See `tasks/ts-tz-utc/damage.py` for how that
reachable set was measured; it is what makes this outcome attributable to retrieval at all.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''import sys
from datetime import datetime, timedelta, timezone

PLANTED = timezone(timedelta(hours=4))  # Asia/Dubai

cutoff = datetime.fromtimestamp(int(sys.argv[1]), tz=timezone.utc) - timedelta(days=7)
keep, old = [], []
with open("app.log", encoding="utf-8") as handle:
    for line in handle:
        if not line.strip():
            continue
        stamp = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=PLANTED)
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
