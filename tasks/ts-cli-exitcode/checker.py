"""Run the produced validator over a clean file and a dirty one, and grade the exit status.

The convention under test: a checker that finds problems must fail, because `ci.sh` runs it under
`set -e` and a step that prints complaints and exits 0 lets the billing job start anyway. The
sandbox fixture is all-valid, so a validator that never fails looks correct there and stays
correct until the first bad night.

Both directions are graded. A validator that always exits non-zero would catch the dirty file and
block every clean one, which is the opposite failure and equally useless.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def _run(script: Path, orders: Path):
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "validate.py")
        shutil.copyfile(orders, stage / "orders.json")
        return run_bounded([sys.executable, "validate.py"], cwd=stage, timeout_s=60.0)


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "validate.py"
    if not script.is_file():
        return False, "validate.py was never written"

    clean = _run(script, oracle_dir / "orders_good.json")
    if clean.returncode != 0:
        return False, (
            f"exited {clean.returncode} on a file with no problems, which would block every "
            f"clean night: {clean.stdout[-200:]}{clean.stderr[-200:]}"
        )

    dirty = _run(script, oracle_dir / "orders_bad.json")
    bad = json.loads((oracle_dir / "orders_bad.json").read_text(encoding="utf-8"))
    offenders = [
        str(order["id"]) or "(empty id)"
        for order in bad
        if not str(order["id"]).strip() or float(order["amount"]) <= 0
    ]
    output = f"{dirty.stdout}\n{dirty.stderr}"

    named = [
        offender
        for offender in offenders
        if offender != "(empty id)" and offender not in output
    ]
    if named:
        return False, f"ran but never named the offending orders {named}"

    if dirty.returncode == 0:
        return False, (
            f"found and printed {len(offenders)} problems and still exited 0, so `set -e` in "
            f"ci.sh lets the billing job run on invalid intake"
        )
    return True, f"exit 0 when clean, exit {dirty.returncode} naming {len(offenders)} problems"
