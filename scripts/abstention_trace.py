"""Run the observed-decision contract over a completed benchmark run."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from harness.abstention import declines
from harness.calibration import audit_record_labels, calibrate
from harness.decision_trace import DECISION_STAGES, evaluate_record
from harness.io import read_jsonl


def _discarded(run_dir: Path) -> set[tuple[str, int]]:
    report = json.loads((run_dir / "admission.json").read_text(encoding="utf-8"))
    return {(str(cell[0]), int(cell[1])) for cell in report.get("discarded_cells", ())}


def _condition_dirs(results_root: Path, run_id: str) -> list[tuple[str, Path]]:
    prefix = f"{run_id}-"
    discovered = sorted(
        (path.name.removeprefix(prefix), path)
        for path in results_root.iterdir()
        if path.is_dir() and path.name.startswith(prefix)
    )
    if discovered:
        return discovered

    # Direct pilot runs use the run id as the directory name. The wrapper adds the condition
    # suffix, so the old discovery logic silently produced an empty analysis for a valid direct
    # run. Recover the condition from the environment or the first record when available.
    direct = results_root / run_id
    records_path = direct / "records.final.jsonl"
    if not records_path.is_file():
        return []
    condition = ""
    environment_path = direct / "environment.json"
    if environment_path.is_file():
        environment = json.loads(environment_path.read_text(encoding="utf-8"))
        condition = str(environment.get("condition") or "")
    if not condition:
        with records_path.open(encoding="utf-8") as source:
            first = next((line for line in source if line.strip()), "")
        if first:
            record = json.loads(first)
            metadata = record.get("metadata")
            if isinstance(metadata, dict):
                condition = str(metadata.get("condition") or "")
    return [(condition, direct)]


def analyze_run(
    results_root: Path,
    run_id: str,
    *,
    threshold: float | None = None,
    labels: dict[str, bool] | None = None,
    label_source_sha256: str | None = None,
    label_source_name: str | None = None,
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
        environment_path = run_dir / "environment.json"
        environment = (
            json.loads(environment_path.read_text(encoding="utf-8"))
            if environment_path.is_file()
            else {}
        )
        decision_output = environment.get("decision_output", {})
        required_stages = (
            DECISION_STAGES
            if isinstance(decision_output, dict) and decision_output.get("staged")
            else None
        )
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
                result = evaluate_record(
                    record.to_dict(),
                    threshold=threshold,
                    required_stages=required_stages,
                )
                statuses[result["status"]] += 1
                abstentions += int(result["abstention_observed"])
                text_markers += int(declines(record.response)[0])
                confidence_observations += result["n_confidence_scores"]
                row = record.to_dict()
                row["condition"] = condition
                admitted_records.append(row)
            total.update(statuses)
            stage_counts = Counter()
            complete_stages = 0
            incomplete_stages = 0
            for record in rows:
                stage_report = evaluate_record(
                    record.to_dict(),
                    threshold=threshold,
                    required_stages=required_stages,
                )["stage_completeness"]
                stage_counts.update(stage_report["observed"])
                if stage_report["complete"]:
                    complete_stages += 1
                elif required_stages:
                    incomplete_stages += 1
            by_arm[arm] = {
                "n_admitted": len(rows),
                "contract_status": dict(sorted(statuses.items())),
                "abstention_observed": abstentions,
                "response_text_marker_matches_not_used_by_contract": text_markers,
                "decision_stages": {
                    "required": list(required_stages or ()),
                    "observed_records_by_stage": {
                        stage: stage_counts[stage] for stage in DECISION_STAGES
                    },
                    "records_complete": complete_stages,
                    "records_incomplete": incomplete_stages,
                },
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
            label_source_name=label_source_name,
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
    label_source_name: str | None,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    if confidence_observations == 0:
        return {
            "status": "not_observed",
            "n_confidence_scores": 0,
            "label_source": None,
            "note": "This run emitted no confidence values, so calibration and AUC were not observed.",
        }
    if labels is None:
        return {
            "status": "requires_labels",
            "n_confidence_scores": confidence_observations,
            "label_source": None,
            "note": (
                "This run emitted confidence values, but AUC and probability calibration require "
                "independently labelled examples. Re-run with --labels <file>."
            ),
        }
    audit = audit_record_labels(records, labels)
    examples = audit["examples"]
    result: dict[str, Any] = {
        "status": "labelled",
        "n_confidence_scores": confidence_observations,
        "n_labelled_examples": len(examples),
        "label_source_sha256": label_source_sha256,
        "label_source": {
            "name": label_source_name,
            "sha256": label_source_sha256,
            "format": "json object or array",
        },
        "included_records": audit["included_records"],
        "excluded_records": audit["excluded_records"],
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
        label_source_name=args.labels.name if args.labels is not None else None,
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
