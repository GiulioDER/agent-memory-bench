"""Drive the produced client.py with an injected failing transport and a fake sleep.

The convention under test: retry delays grow exponentially, are capped at 30 seconds, and
carry jitter; a fixed sleep between attempts is the thundering-herd shape the incident
banned. The driver injects the transport and records the requested delays, so no wall-clock
time is spent and the delay sequence itself is what gets graded.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    module = workdir / "client.py"
    if not module.is_file():
        return False, "client.py is missing from the sandbox"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(module, stage / "client.py")
        shutil.copyfile(oracle_dir / "driver.py", stage / "driver.py")
        completed = run_bounded([sys.executable, "driver.py"], cwd=stage, timeout_s=60.0)

    for line in completed.stdout.splitlines():
        if line.startswith("VERDICT "):
            verdict = line[len("VERDICT ") :]
            if verdict == "BACKOFF_OK":
                return True, "delays grow, cap at 30, and are not constant"
            return False, f"retry behaviour violates the convention: {verdict}"
    return False, (
        f"driver died before a verdict (exit {completed.returncode}): {completed.stderr[-500:]}"
    )
