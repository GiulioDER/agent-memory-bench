"""The competent solution WITHOUT the fact: retry with a one-second sleep between attempts.

It retries the right number of times, returns the right result, and propagates the right
error; every fixture path passes. The constant delay is what synchronises a fleet into a
thundering herd, and nothing in the sandbox can show that.
"""

from pathlib import Path

NEW_CLIENT = '''"""Feed fetching for the syncer."""

import time


class TransportError(Exception):
    """Raised by a transport when a fetch attempt fails."""


def fetch(url, transport, sleep=time.sleep):
    """Fetch ``url`` via ``transport`` and return its response text, retrying on failure."""
    last_error = None
    for attempt in range(8):
        try:
            return transport(url)
        except TransportError as error:
            last_error = error
            if attempt < 7:
                sleep(1)
    raise last_error
'''


def apply(workdir: Path) -> None:
    (workdir / "client.py").write_text(NEW_CLIENT, encoding="utf-8")
