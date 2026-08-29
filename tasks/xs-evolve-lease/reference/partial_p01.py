"""Retrieved the 2026-04-12 session only: 90 seconds, the first value.

It must fail. A corpus that holds three revisions of one number and grades none of them
as stale would reward retrieving the most similar session rather than the current one."""

from pathlib import Path

BODY = '''

def heartbeat(lease_id, renew, sleep, should_continue):
    """Hold the queue lease open while the drain runs."""

    while should_continue():
        renew(lease_id)
        sleep(90)
'''


def apply(workdir: Path) -> None:
    target = workdir / "worker.py"
    target.write_text(target.read_text(encoding="utf-8") + BODY, encoding="utf-8")
