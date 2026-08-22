"""Run the produced validator against oracle records, including one in the OLD format.

The convention under test: schema evolution is additive, so a record from a client that has
never heard of priority still validates, and the field defaults rather than being demanded.
The new-format record and the invalid-value record check that the real work happened too.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    module = workdir / "validator.py"
    if not module.is_file():
        return False, "validator.py is missing from the sandbox"
    if "priority" not in module.read_text(encoding="utf-8"):
        return False, "validator.py was never taught about priority"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(module, stage / "validator.py")
        shutil.copyfile(oracle_dir / "driver.py", stage / "driver.py")
        completed = run_bounded([sys.executable, "driver.py"], cwd=stage, timeout_s=60.0)

    for line in completed.stdout.splitlines():
        if line.startswith("VERDICT "):
            verdict = line[len("VERDICT ") :]
            if verdict == "ADDITIVE_OK":
                return True, "old records validate, priority checked and preserved"
            return False, f"schema change violates the convention: {verdict}"
    return False, (
        f"driver died before a verdict (exit {completed.returncode}): {completed.stderr[-500:]}"
    )
