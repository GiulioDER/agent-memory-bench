"""Consolidate supplier files whose order ids collide across suppliers.

The approach the corpus records as having failed is keying on `order_id` alone. Every id in the
sandbox is unique, so that works on everything a session can see and loses records only here,
where two suppliers reuse an id range.

⚠️ **This checker asserts PROPERTIES, not one expected output, and that is deliberate.** The
corpus records an outcome and never a rule, so the agent must infer an exclusion and then choose
freely: keying on (supplier, order_id), or on that plus the payload, are both correct and both
pass. Every other checker in this suite compares against a single expected artefact, which admits
exactly one solution and is brittle in a way a failed-approach task must not be.

Three properties, and each catches a different wrong answer:

    nothing lost        keying on `order_id` alone drops the second supplier's orders
    nothing duplicated  keying on the WHOLE record keeps redeliveries, which differ in
                        `received_at` only
    order preserved     the spec asks for first-seen order
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

#: What makes two lines the same ORDER. `received_at` is excluded: a redelivered file carries a
#: later one for an order that is otherwise identical.
#:
#: ⚠️ No record carries a `supplier`. That is the trap: the file a record came from is the only
#: thing that separates two suppliers reusing an id range, and nothing INSIDE a record says so.
#: The first version of this task put a supplier field on every line, and the calibration screen
#: measured `bare` at 3/3 because all three sessions reached for a tuple key that included it.
IDENTITY = ("order_id", "sku", "qty")


def _key(record: dict) -> tuple:
    return tuple(record.get(field) for field in IDENTITY)


def _expected(oracle_dir: Path) -> list[tuple]:
    seen: list[tuple] = []
    for path in sorted((oracle_dir / "orders").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            key = _key(json.loads(line))
            if key not in seen:
                seen.append(key)
    return seen


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "consolidate.py"
    if not script.is_file():
        return False, "consolidate.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "consolidate.py")
        shutil.copytree(oracle_dir / "orders", stage / "orders")
        shutil.copyfile(oracle_dir / "driver.py", stage / "driver.py")
        completed = run_bounded([sys.executable, "driver.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, f"driver exited {completed.returncode}: {completed.stderr[-500:]}"
        try:
            produced = json.loads(completed.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return False, f"driver printed no result: {completed.stdout[-200:]}"

    if not isinstance(produced, list) or not all(isinstance(r, dict) for r in produced):
        return False, "consolidate did not return a list of order records"

    expected = _expected(oracle_dir)
    got = [_key(record) for record in produced]

    duplicates = len(got) - len(set(got))
    if duplicates:
        return False, (
            f"{duplicates} redelivered order(s) survived: records that differ only in "
            f"received_at were treated as distinct"
        )

    lost = [key for key in expected if key not in set(got)]
    if lost:
        ids = sorted({key[0] for key in lost})
        return False, (
            f"{len(lost)} real order(s) were dropped, at order_id(s) {ids}: two supplier files "
            f"reuse an id range, so order_id alone is not an identity"
        )

    invented = [key for key in got if key not in set(expected)]
    if invented:
        return False, f"{len(invented)} record(s) are not in the input at all"

    if got != expected:
        return False, "every order is present exactly once, but not in first-seen order"

    return True, f"{len(got)} distinct orders, {len(expected)} expected, order preserved"
