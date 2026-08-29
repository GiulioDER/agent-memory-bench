"""Retrieved p02 only: oldest `recorded_at` first, in one call.

The other half. It must fail for the same reason.
"""

from pathlib import Path

SCRIPT = '''\
def push(records, send):
    send(sorted(records, key=lambda row: row["recorded_at"]))
'''


def apply(workdir: Path) -> None:
    (workdir / "push.py").write_text(SCRIPT, encoding="utf-8")
