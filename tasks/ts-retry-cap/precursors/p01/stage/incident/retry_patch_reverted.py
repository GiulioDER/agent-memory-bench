"""client.py retry patch as deployed 2026-08-10, reverted 2026-08-13. Kept for the incident review."""

import time


class TransportError(Exception):
    """Raised by a transport when a fetch attempt fails."""


def fetch(url, transport, sleep=time.sleep):
    """Fetch ``url`` via ``transport``, retrying until it answers."""
    while True:
        try:
            return transport(url)
        except TransportError:
            sleep(1.0)
