"""Compute confidence calibration and AUC from a labelled JSON query set.

The input is a JSON array of objects with ``id``, ``confidence`` and ``answerable`` fields. The
labels must be authored independently of the scores. An uncertified fit is reported and blocked
from runtime use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from harness.calibration import CalibrationExample, audit_record_labels, calibrate
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
            base = f"{row.get('task_id')}/{row.get('seed', 0)}/{row.get('arm')}"
            key = f"{row['condition']}/{base}" if row.get("condition") else base
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
    parser.add_argument("--output", type=Path, help="also write the calibration result to this path")
    args = parser.parse_args()
    if args.records is not None:
        if args.labels is None:
            raise SystemExit("--labels is required with --records")
        label_bytes = args.labels.read_bytes()
        labels = _labels(json.loads(label_bytes.decode("utf-8")))
        audit = audit_record_labels(
            (record.to_dict() for record in read_jsonl(args.records)), labels
        )
        examples = audit["examples"]
    else:
        if args.examples is None:
            raise SystemExit("provide an examples JSON file or --records with --labels")
        raw = json.loads(args.examples.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise SystemExit("calibration input must be a JSON array")
        if not all(isinstance(value, dict) for value in raw):
            raise SystemExit("calibration input rows must be JSON objects")
        examples = [CalibrationExample.from_mapping(value) for value in raw]
    result = calibrate(examples, draws=args.draws, seed=args.seed)
    if args.records is not None:
        result["label_source"] = {
            "name": args.labels.name,
            "sha256": hashlib.sha256(label_bytes).hexdigest(),
            "format": "json object or array",
        }
        result["included_records"] = audit["included_records"]
        result["excluded_records"] = audit["excluded_records"]
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8", newline="\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
