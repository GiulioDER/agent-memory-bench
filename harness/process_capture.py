"""Bounded text capture for subprocess pipes."""

from __future__ import annotations

from threading import Thread
from typing import TextIO

MAX_CAPTURE_CHARS = 1_048_576
TRUNCATION_MARKER = "\n[output truncated after 1048576 characters]"


def start_output_drainers(
    stdout: TextIO | None,
    stderr: TextIO | None,
) -> tuple[tuple[Thread, ...], dict[str, list[str]], dict[str, bool]]:
    """Drain both pipes continuously while retaining at most one bounded prefix each."""

    buffers = {"stdout": [], "stderr": []}
    truncated = {"stdout": False, "stderr": False}
    threads: list[Thread] = []

    def drain(name: str, stream: TextIO | None) -> None:
        if stream is None:
            return
        retained = 0
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                remaining = MAX_CAPTURE_CHARS - retained
                if remaining > 0:
                    buffers[name].append(chunk[:remaining])
                    retained += min(len(chunk), remaining)
                if len(chunk) > remaining:
                    truncated[name] = True
        except (OSError, ValueError):
            return

    for name, stream in (("stdout", stdout), ("stderr", stderr)):
        thread = Thread(target=drain, args=(name, stream), daemon=True)
        thread.start()
        threads.append(thread)
    return tuple(threads), buffers, truncated


def finish_output_drainers(
    drainers: tuple[Thread, ...],
    buffers: dict[str, list[str]],
    truncated: dict[str, bool],
) -> tuple[str, str]:
    """Join pipe readers and return bounded diagnostics with explicit truncation markers."""

    for thread in drainers:
        thread.join(timeout=10)
    output: dict[str, str] = {}
    for name in ("stdout", "stderr"):
        value = "".join(buffers[name])
        if truncated[name]:
            value += TRUNCATION_MARKER
        output[name] = value
    return output["stdout"], output["stderr"]
