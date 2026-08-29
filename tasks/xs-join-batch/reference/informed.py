"""Both halves: oldest `recorded_at` first, in batches of exactly 25."""

from pathlib import Path

SCRIPT = '''\
BATCH = 25


def push(records, send):
    rows = sorted(records, key=lambda row: row["recorded_at"])
    for start in range(0, len(rows), BATCH):
        send(rows[start : start + BATCH])
'''


def apply(workdir: Path) -> None:
    (workdir / "push.py").write_text(SCRIPT, encoding="utf-8")
