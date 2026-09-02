"""Run the observed-decision contract over a completed benchmark run."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from harness.abstention import declines
from harness.decision_trace import evaluate_record
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
    results_root: Path, run_id: str, *, threshold: float | None = None
) -> dict[str, Any]:
    """Analyze admitted records and leave response keyword matching as a comparison only."""

    by_condition: dict[str, Any] = {}
    total = Counter()
    confidence_observations = 0
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
        "calibration": {
            "status": (
                "not_observed" if confidence_observations == 0 else "requires_labels"
            ),
            "n_confidence_scores": confidence_observations,
            "note": (
                "AUC and probability calibration require independently labelled examples. "
                "No confidence trace was recorded in this run."
            ),
        },
        "conditions": by_condition,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-root", type=Path, default=Path("results"))
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()
    report = analyze_run(args.results_root, args.run_id, threshold=args.threshold)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
