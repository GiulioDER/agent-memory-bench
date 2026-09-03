"""Run the observed-decision contract over a completed benchmark run."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from harness.abstention import declines
from harness.decision_trace import evaluate_record
from harness.calibration import calibrate, examples_from_records
from harness.io import read_jsonl


def _discarded(run_dir: Path) -> set[tuple[str, int]]:
    report = json.loads((run_dir / "admission.json").read_text(encoding="utf-8"))
    return {(str(cell[0]), int(cell[1])) for cell in report.get("discarded_cells", ())}


def _condition_dirs(results_root: Path, run_id: str) -> list[tuple[str, Path]]:
    prefix = f"{run_id}-"
    return sorted(
        (path.name.removeprefix(prefix), path)
        for path in results_root.iterdir()
        if path.is_dir() and path.name.startswith(prefix)
    )


def analyze_run(
    results_root: Path,
    run_id: str,
    *,
    threshold: float | None = None,
    labels: dict[str, bool] | None = None,
    label_source_sha256: str | None = None,
    calibration_draws: int = 10_000,
    calibration_seed: int = 20260902,
) -> dict[str, Any]:
    """Analyze admitted records and leave response keyword matching as a comparison only."""

    by_condition: dict[str, Any] = {}
    total = Counter()
    confidence_observations = 0
    admitted_records = []
    for condition, run_dir in _condition_dirs(results_root, run_id):
        records = read_jsonl(run_dir / "records.final.jsonl")
        discarded = _discarded(run_dir) if (run_dir / "admission.json").is_file() else set()
        by_arm: dict[str, Any] = {}
        for arm in sorted({record.arm for record in records}):
            rows = [
                record
                for record in records
                if record.arm == arm and record.cell not in discarded
            ]
            statuses = Counter()
            text_markers = 0
            abstentions = 0
            for record in rows:
                result = evaluate_record(record.to_dict(), threshold=threshold)
                statuses[result["status"]] += 1
                abstentions += int(result["abstention_observed"])
                text_markers += int(declines(record.response)[0])
                confidence_observations += result["n_confidence_scores"]
                row = record.to_dict()
                row["condition"] = condition
                admitted_records.append(row)
            total.update(statuses)
            by_arm[arm] = {
                "n_admitted": len(rows),
                "contract_status": dict(sorted(statuses.items())),
                "abstention_observed": abstentions,
                "response_text_marker_matches_not_used_by_contract": text_markers,
            }
        by_condition[condition] = by_arm
    return {
        "run_id": run_id,
        "threshold": threshold,
        "contract": {
            "by_status": dict(sorted(total.items())),
            "note": (
                "Final response text is reported only as a comparison. It cannot create an "
                "observed runtime decision. Calibration is not evaluated here."
            ),
        },
        "calibration": _calibration_report(
            admitted_records,
            confidence_observations=confidence_observations,
            labels=labels,
            label_source_sha256=label_source_sha256,
            draws=calibration_draws,
            seed=calibration_seed,
        ),
        "conditions": by_condition,
    }


def _calibration_report(
    records: list[dict[str, Any]],
    *,
    confidence_observations: int,
    labels: dict[str, bool] | None,
    label_source_sha256: str | None,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    if confidence_observations == 0:
        return {
            "status": "not_observed",
            "n_confidence_scores": 0,
            "note": "This run emitted no confidence values, so calibration and AUC were not observed.",
        }
    if labels is None:
        return {
            "status": "requires_labels",
            "n_confidence_scores": confidence_observations,
            "note": (
                "This run emitted confidence values, but AUC and probability calibration require "
                "independently labelled examples. Re-run with --labels <file>."
            ),
        }
    examples = examples_from_records(records, labels)
    result: dict[str, Any] = {
        "status": "labelled",
        "n_confidence_scores": confidence_observations,
        "n_labelled_examples": len(examples),
        "label_source_sha256": label_source_sha256,
    }
    try:
        result["metrics"] = calibrate(examples, draws=draws, seed=seed)
    except ValueError as exc:
        result["status"] = "insufficient_labels"
        result["error"] = str(exc)
    return result


def _labels(value: object) -> dict[str, bool]:
    if isinstance(value, dict):
        if not all(isinstance(key, str) and isinstance(label, bool) for key, label in value.items()):
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
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-root", type=Path, default=Path("results"))
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--labels", type=Path, help="independent answerability labels JSON")
    parser.add_argument("--draws", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--output", type=Path, help="also write the JSON report to this path")
    args = parser.parse_args()
    labels = None
    digest = None
    if args.labels is not None:
        raw = args.labels.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        labels = _labels(json.loads(raw.decode("utf-8")))
    report = analyze_run(
        args.results_root,
        args.run_id,
        threshold=args.threshold,
        labels=labels,
        label_source_sha256=digest,
        calibration_draws=args.draws,
        calibration_seed=args.seed,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8", newline="\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
