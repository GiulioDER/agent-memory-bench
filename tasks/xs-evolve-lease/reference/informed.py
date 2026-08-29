"""The current decision, 2026-07-21: renew every 20 seconds.

The third session states it as final. Nothing in the fixture points at 20."""

from pathlib import Path

BODY = '''

def heartbeat(lease_id, renew, sleep, should_continue):
    """Hold the queue lease open while the drain runs."""

    while should_continue():
        renew(lease_id)
        sleep(20)
'''


def apply(workdir: Path) -> None:
    target = workdir / "worker.py"
    target.write_text(target.read_text(encoding="utf-8") + BODY, encoding="utf-8")
