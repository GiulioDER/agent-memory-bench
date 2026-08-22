"""Generate export.csv from orders.json."""

import json
from pathlib import Path

COLUMNS = ["id", "sku", "qty"]


def main() -> None:
    orders = json.loads(Path("orders.json").read_text(encoding="utf-8"))
    lines = [",".join(COLUMNS)]
    for order in orders:
        lines.append(",".join(str(order[column]) for column in COLUMNS))
    Path("export.csv").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
