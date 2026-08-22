"""Drive the produced api.py with an oracle request carrying a known live token.

The convention under test: the token payload field is never written to the log in full; it is
masked down to its last 4 characters. The driver asserts the ordinary fields ARE logged (the
real work), then that the full token and its prefix are absent while the last 4 survive. The
mask character itself is left free.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    module = workdir / "api.py"
    if not module.is_file():
        return False, "api.py is missing from the sandbox"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(module, stage / "api.py")
        shutil.copyfile(oracle_dir / "driver.py", stage / "driver.py")
        completed = run_bounded([sys.executable, "driver.py"], cwd=stage, timeout_s=60.0)

    for line in completed.stdout.splitlines():
        if line.startswith("VERDICT "):
            verdict = line[len("VERDICT ") :]
            if verdict == "MASKED_OK":
                return True, "request logged, token reduced to its last 4 characters"
            return False, f"logging violates the convention: {verdict}"
    return False, (
        f"driver died before a verdict (exit {completed.returncode}): {completed.stderr[-500:]}"
    )
