"""Validate a longitudinal plan before launching any model sessions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness.sequence_plan import load_plan_file
from harness.sequence_validation import validate_plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--tasks-root", type=Path, default=Path("tasks"))
    parser.add_argument("--shared-file", type=Path, action="append", default=[])
    parser.add_argument("--chains-per-length", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    validation = validate_plan(
        load_plan_file(args.plan),
        tasks_root=args.tasks_root,
        shared_files=args.shared_file,
        expected_chains_per_length=args.chains_per_length,
    )
    payload = validation.to_dict()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
