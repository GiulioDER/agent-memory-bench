"""Retrieved p01 only: batches of exactly 25, in the order the collector wrote them.

Half the rule. It must fail, or the task is not measuring synthesis: a session that found one
session out of two would score as a success and the second session would be decoration.
"""

from pathlib import Path

SCRIPT = '''\
BATCH = 25


def push(records, send):
    rows = list(records)
    for start in range(0, len(rows), BATCH):
        send(rows[start : start + BATCH])
'''


def apply(workdir: Path) -> None:
    (workdir / "push.py").write_text(SCRIPT, encoding="utf-8")
