"""Retrieved the 2026-06-02 session only: 45 seconds, the second value.

Also stale, and also must fail. It is the middle revision, which is the one a
similarity search is most likely to surface alongside the others."""

from pathlib import Path

BODY = '''

def heartbeat(lease_id, renew, sleep, should_continue):
    """Hold the queue lease open while the drain runs."""

    while should_continue():
        renew(lease_id)
        sleep(45)
'''


def apply(workdir: Path) -> None:
    target = workdir / "worker.py"
    target.write_text(target.read_text(encoding="utf-8") + BODY, encoding="utf-8")
