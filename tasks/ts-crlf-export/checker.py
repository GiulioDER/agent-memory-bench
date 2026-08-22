"""Run the produced export script on oracle orders, then read the export as BYTES.

Bytes are the convention under test: the fulfilment partner requires CRLF line endings, so
this is the one comparison that must not be parsed-and-forgiving about them. Row content is
still compared parsed, because field formatting is not what the task is about. The expected
CRLF bytes are asserted at runtime against what the script wrote, never stored in git, so
no .gitattributes handling is needed for this task.
"""

from __future__ import annotations

import csv
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

HEADER = ["id", "sku", "qty", "region"]


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "export_orders.py"
    if not script.is_file():
        return False, "export_orders.py is gone"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "export_orders.py")
        shutil.copyfile(oracle_dir / "orders.json", stage / "orders.json")
        completed = run_bounded(
            [sys.executable, "export_orders.py"], cwd=stage, timeout_s=60.0
        )
        if completed.returncode != 0:
            return False, f"export_orders.py exited {completed.returncode}: {completed.stderr[-500:]}"
        produced_path = stage / "export.csv"
        if not produced_path.is_file():
            return False, "export_orders.py ran but wrote no export.csv"
        data = produced_path.read_bytes()

    if not data:
        return False, "export.csv is empty"
    if data.count(b"\n") != data.count(b"\r\n") or b"\r\n" not in data:
        lf_only = data.count(b"\n") - data.count(b"\r\n")
        return False, (
            f"line endings are not CRLF throughout ({lf_only} bare-LF endings); "
            "the fulfilment consumer drops such exports"
        )

    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    if not rows or rows[0] != HEADER:
        return False, f"header is {rows[0] if rows else 'missing'}, expected {HEADER}"
    orders = json.loads((oracle_dir / "orders.json").read_text(encoding="utf-8"))
    expected = [[str(order[column]) for column in HEADER] for order in orders]
    if rows[1:] != expected:
        return False, f"rows differ from the oracle orders: got {rows[1:4]}..."
    return True, f"CRLF export with region, {len(expected)} rows"
