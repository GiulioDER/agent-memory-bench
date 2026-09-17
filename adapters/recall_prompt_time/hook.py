"""Fail-open evidence wrapper around the released RE-call prompt-time hook."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def _trace_path() -> Path | None:
    raw = os.environ.get("AMB_RECALL_PROMPT_TIME_TRACE", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).with_name("prompt-time-ledger.jsonl")


def _write_trace(entry: dict[str, Any]) -> None:
    path = _trace_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as sink:
        sink.write(json.dumps(entry, sort_keys=True) + "\n")


def main() -> int:
    raw_output = ""
    error_name: str | None = None
    try:
        source_root = os.environ.get("AMB_RECALL_HOOK_SOURCE_ROOT", "").strip()
        source_root = source_root or str(Path(__file__).parent)
        sys.path.insert(0, source_root)
        from recall_hooks.prompt_time import user_prompt_submit

        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            raise TypeError("hook input is not an object")
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            user_prompt_submit(payload)
        raw_output = captured.getvalue()
        if raw_output:
            sys.stdout.write(raw_output)
    except Exception as error:  # noqa: BLE001 - prompt-time hook must always fail open
        error_name = type(error).__name__
    stems = re.findall(r"^- ([^\s]+) \(score", raw_output, flags=re.MULTILINE)
    _write_trace(
        {
            "event": "UserPromptSubmit",
            "exit_code": 0,
            "hook_error": error_name,
            "injection_status": "context" if raw_output else "empty",
            "output_bytes": len(raw_output.encode("utf-8")),
            "output_sha256": hashlib.sha256(raw_output.encode("utf-8")).hexdigest(),
            "source_count": len(stems),
            "source_sha256": [hashlib.sha256(stem.encode("utf-8")).hexdigest() for stem in stems],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
