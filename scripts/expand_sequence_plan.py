"""Expand a validated longitudinal plan into runner rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness.sequence_plan import load_plan_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = load_plan_file(args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in plan.rows()) + "\n",
        encoding="utf-8",
    )
    print(f"expanded {len(plan.rows())} rows from {plan.plan_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
