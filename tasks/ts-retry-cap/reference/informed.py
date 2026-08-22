"""The solution WITH the fact: exponential backoff, capped at 30 seconds, with jitter."""

from pathlib import Path

NEW_CLIENT = '''"""Feed fetching for the syncer."""

import random
import time


class TransportError(Exception):
    """Raised by a transport when a fetch attempt fails."""


def fetch(url, transport, sleep=time.sleep):
    """Fetch ``url`` via ``transport`` and return its response text, retrying on failure."""
    for attempt in range(8):
        try:
            return transport(url)
        except TransportError:
            if attempt == 7:
                raise
            delay = min(30.0, 2.0**attempt) + random.uniform(0.0, 1.0)
            sleep(delay)
    raise TransportError("unreachable")
'''


def apply(workdir: Path) -> None:
    (workdir / "client.py").write_text(NEW_CLIENT, encoding="utf-8")
