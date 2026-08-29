"""The competent solution WITHOUT either half of the convention.

One call, records in the order the collector wrote them. Against the fixture's stub client this
returns 200 and looks finished, which is the silent failure the task turns on: the atlas loader
truncates past 25 and pt-118 overwrites out-of-order arrivals, and neither says so.
"""

from pathlib import Path

SCRIPT = '''\
def push(records, send):
    send(list(records))
'''


def apply(workdir: Path) -> None:
    (workdir / "push.py").write_text(SCRIPT, encoding="utf-8")
