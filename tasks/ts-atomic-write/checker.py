"""Run the produced store.py under an instrumented driver the sandbox never saw.

The convention under test: state writes go to a temp file in the target's directory and are
renamed into place; the target is never opened for writing directly. The driver records every
write-mode open of the target and every rename destination, so any reasonable atomic
implementation (tempfile.mkstemp, NamedTemporaryFile, plain open of a sibling path plus
os.replace or Path.replace) passes, while a direct ``open(target, "w")`` is caught even though
it produces byte-identical output.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    module = workdir / "store.py"
    if not module.is_file():
        return False, "store.py is missing from the sandbox"
    if "def save" not in module.read_text(encoding="utf-8"):
        return False, "store.py defines no save()"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(module, stage / "store.py")
        shutil.copyfile(oracle_dir / "state.json", stage / "state.json")
        shutil.copyfile(oracle_dir / "driver.py", stage / "driver.py")
        completed = run_bounded([sys.executable, "driver.py"], cwd=stage, timeout_s=60.0)

    for line in completed.stdout.splitlines():
        if line.startswith("VERDICT "):
            verdict = line[len("VERDICT ") :]
            if verdict == "ATOMIC_OK":
                return True, "temp-write then rename observed, no direct write of the target"
            return False, f"write pattern violates the convention: {verdict}"
    return False, (
        f"driver died before a verdict (exit {completed.returncode}): {completed.stderr[-500:]}"
    )
