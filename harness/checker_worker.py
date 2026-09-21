"""Minimal stdin to stdout worker for the networkless trusted checker container."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import traceback
from pathlib import Path
from typing import Any

MAX_REQUEST_BYTES = 64 * 1024
TASK_ID = re.compile(r"[a-z0-9][a-z0-9-]*")


class CheckerRequestError(ValueError):
    """The controller supplied an invalid checker request."""


def _checker(path: Path):
    spec = importlib.util.spec_from_file_location(
        f"_isolated_checker_{path.parent.name}", path
    )
    if spec is None or spec.loader is None:
        raise CheckerRequestError("checker module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    check = getattr(module, "check", None)
    if not callable(check):
        raise CheckerRequestError("checker module defines no check function")
    return check


def evaluate(
    request: object,
    *,
    bench_root: Path = Path("/bench"),
    artifact_root: Path = Path("/artifact"),
    oracle_root: Path = Path("/oracle"),
) -> dict[str, Any]:
    """Execute one bundled checker against the two exact read only mount roots."""
    if not isinstance(request, dict):
        raise CheckerRequestError("checker request must be an object")
    task_id = request.get("task_id")
    if not isinstance(task_id, str) or TASK_ID.fullmatch(task_id) is None:
        raise CheckerRequestError("task_id is invalid")
    if request.get("artifact") != str(artifact_root):
        raise CheckerRequestError("artifact must name the mounted artifact root")
    if request.get("oracle_root") != str(oracle_root):
        raise CheckerRequestError("oracle_root must name the mounted oracle root")
    checker_path = bench_root / "tasks" / task_id / "checker.py"
    if not checker_path.is_file():
        raise CheckerRequestError("task_id has no bundled checker")
    check = _checker(checker_path)
    try:
        ok, verdict = check(artifact_root, oracle_root)
    except Exception as error:  # noqa: BLE001, an unreadable deliverable is a failed task
        detail = "".join(traceback.format_exception_only(type(error), error)).strip()
        ok, verdict = False, f"checker raised: {detail}"
    return {
        "checker_status": "completed",
        "ok": bool(ok),
        "verdict": str(verdict),
        "timed_out": False,
    }


def main() -> None:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        raise SystemExit("checker request is too large")
    try:
        request = json.loads(raw.decode("utf-8"))
        result = evaluate(request)
    except (CheckerRequestError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {
                    "checker_status": "error",
                    "diagnostics": {"error_class": type(error).__name__},
                },
                sort_keys=True,
            )
        )
        raise SystemExit(2) from error
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
