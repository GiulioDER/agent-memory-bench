"""The solution WITH the fact: the fulfilment consumer requires CRLF line endings."""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
"""Generate export.csv from orders.json.

The fulfilment consumer requires CRLF line endings; a bare-LF export is dropped.
"""

import json
from pathlib import Path

COLUMNS = ["id", "sku", "qty", "region"]


def main() -> None:
    orders = json.loads(Path("orders.json").read_text(encoding="utf-8"))
    lines = [",".join(COLUMNS)]
    for order in orders:
        lines.append(",".join(str(order[column]) for column in COLUMNS))
    body = "\\r\\n".join(lines) + "\\r\\n"
    Path("export.csv").write_text(body, encoding="utf-8", newline="")


if __name__ == "__main__":
    main()
'''


def apply(workdir: Path) -> None:
    (workdir / "export_orders.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "export_orders.py"], cwd=workdir, check=True, timeout=60)
