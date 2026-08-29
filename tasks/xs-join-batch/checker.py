"""Grade push.py against oracle records, one verdict per half of the distributed convention.

The convention is two rules recorded in two sessions months apart, under two names for one
partner: batches of exactly 25 (the atlas loader truncates silently beyond that) and oldest
`recorded_at` first (pt-118 overwrites out-of-order arrivals). Passing needs both. The driver
reports which half landed, so `ORDER_OK_BATCHING_WRONG` and `BATCHING_OK_ORDER_WRONG` are
recorded as distinct failures rather than as one undifferentiated zero.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

_VERDICTS = {
    "NO_SEND_CALLS": "push.py never called send",
    "EMPTY_BATCH": "an empty batch was sent",
    "BATCHING_OK_ORDER_WRONG": "batched correctly, but records were not sent oldest first",
}


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    module = workdir / "push.py"
    if not module.is_file():
        return False, "push.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(module, stage / "push.py")
        shutil.copyfile(oracle_dir / "outbox.jsonl", stage / "outbox.jsonl")
        shutil.copyfile(oracle_dir / "driver.py", stage / "driver.py")
        completed = run_bounded([sys.executable, "driver.py"], cwd=stage, timeout_s=60.0)

    for line in completed.stdout.splitlines():
        if not line.startswith("VERDICT "):
            continue
        verdict = line[len("VERDICT ") :]
        if verdict == "OK":
            return True, "batches of exactly 25, oldest recorded_at first"
        head = verdict.split(":", 1)[0]
        if head == "ORDER_OK_BATCHING_WRONG":
            return False, f"ordered correctly, but batch sizes are {verdict.split(':', 1)[1]}"
        if head == "NEITHER_HALF_APPLIED":
            return False, f"neither half of the convention applied: sizes {verdict.split(':', 1)[1]}"
        if head == "RECORDS_NOT_DELIVERED_EXACTLY_ONCE":
            return False, f"records were not delivered exactly once ({verdict.split(':', 1)[1]} sent)"
        return False, _VERDICTS.get(head, f"convention violated: {verdict}")
    return False, (
        f"driver died before a verdict (exit {completed.returncode}): {completed.stderr[-500:]}"
    )
