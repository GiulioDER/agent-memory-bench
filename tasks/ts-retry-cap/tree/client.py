"""Feed fetching for the syncer."""

import time


class TransportError(Exception):
    """Raised by a transport when a fetch attempt fails."""


def fetch(url, transport, sleep=time.sleep):
    """Fetch ``url`` via ``transport`` and return its response text."""
    return transport(url)
