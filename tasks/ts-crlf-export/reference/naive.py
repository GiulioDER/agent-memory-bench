"""The competent solution WITHOUT the fact: add the column, keep the script's LF endings.

The minimal, reviewable diff adds "region" to COLUMNS and touches nothing else. The existing
script pins newline="\\n", which is the sensible cross-platform default and matches the
repository's own LF normalisation, so the naive engineer keeps it, on either OS. Nothing in
the sandbox ever reads the export back, so the wrong endings surface only downstream.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
"""Generate export.csv from orders.json."""

import json
from pathlib import Path

COLUMNS = ["id", "sku", "qty", "region"]


def main() -> None:
    orders = json.loads(Path("orders.json").read_text(encoding="utf-8"))
    lines = [",".join(COLUMNS)]
    for order in orders:
        lines.append(",".join(str(order[column]) for column in COLUMNS))
    Path("export.csv").write_text("\\n".join(lines) + "\\n", encoding="utf-8", newline="\\n")


if __name__ == "__main__":
    main()
'''


def apply(workdir: Path) -> None:
    (workdir / "export_orders.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "export_orders.py"], cwd=workdir, check=True, timeout=60)
