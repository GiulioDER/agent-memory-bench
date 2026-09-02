"""Compute confidence calibration and AUC from a labelled JSON query set.

The input is a JSON array of objects with ``id``, ``confidence`` and ``answerable`` fields. The
labels must be authored independently of the scores. An uncertified fit is reported and blocked
from runtime use.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness.calibration import CalibrationExample, calibrate, examples_from_records
from harness.io import read_jsonl


def _labels(value: object) -> dict[str, bool]:
    if isinstance(value, dict):
        if not all(
            isinstance(key, str) and isinstance(label, bool)
            for key, label in value.items()
        ):
            raise SystemExit("label mapping values must be booleans")
        return value
    if isinstance(value, list):
        result: dict[str, bool] = {}
        for row in value:
            if not isinstance(row, dict) or not isinstance(row.get("answerable"), bool):
                raise SystemExit("label rows need task_id, seed, arm and boolean answerable")
            key = f"{row.get('task_id')}/{row.get('seed', 0)}/{row.get('arm')}"
            result[key] = row["answerable"]
        return result
    raise SystemExit("labels must be a JSON object or array")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("examples", type=Path, nargs="?")
    parser.add_argument("--records", type=Path)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--draws", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260902)
    args = parser.parse_args()
    if args.records is not None:
        if args.labels is None:
            raise SystemExit("--labels is required with --records")
        labels = _labels(json.loads(args.labels.read_text(encoding="utf-8")))
        examples = examples_from_records(
            (record.to_dict() for record in read_jsonl(args.records)), labels
        )
    else:
        if args.examples is None:
            raise SystemExit("provide an examples JSON file or --records with --labels")
        raw = json.loads(args.examples.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise SystemExit("calibration input must be a JSON array")
        if not all(isinstance(value, dict) for value in raw):
            raise SystemExit("calibration input rows must be JSON objects")
        examples = [CalibrationExample.from_mapping(value) for value in raw]
    print(json.dumps(calibrate(examples, draws=args.draws, seed=args.seed), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
