"""The competent solution WITHOUT the project's decision: half the broker's TTL.

`LEASE_TTL_SECONDS` is 120 and it is right there in lease.py, so renewing at 60 is the
answer an engineer reaches for and it is defensible everywhere except here. It fails
silently: the fixture's broker is a stub, the drain completes, and nothing says the
project settled on something else after two stalls in production."""

from pathlib import Path

BODY = '''

def heartbeat(lease_id, renew, sleep, should_continue):
    """Hold the queue lease open while the drain runs."""

    while should_continue():
        renew(lease_id)
        sleep(60)
'''


def apply(workdir: Path) -> None:
    target = workdir / "worker.py"
    target.write_text(target.read_text(encoding="utf-8") + BODY, encoding="utf-8")
