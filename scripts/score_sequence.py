"""Score longitudinal chains from a records.final.jsonl artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness.io import read_jsonl
from harness.sequence import score_sequences


def render_markdown(analysis: dict) -> str:
    def rate(row: dict, name: str) -> str:
        value = row[name]
        return "unknown" if value is None else f"{value:.3f}"

    def selectivity_value(selectivity: dict, name: str) -> str:
        value = selectivity[name]
        return "unknown" if value is None else f"{value:.3f}"

    def overhead_value(overhead: dict, name: str) -> str:
        value = overhead[name]
        return "unknown" if value is None else str(value)

    lines = [
        "# Sequence and Selectivity Analysis",
        "",
        f"Baseline arm: `{analysis['baseline_arm']}`.",
        "",
        "## Chain outcomes",
        "",
        "| Arm | Length | Admitted chains | Target success | All session success | Paired harm |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in analysis["metrics"]:
        lines.append(
            f"| {row['arm']} | {row['length']} | {row['admitted_chains']} | "
            f"{rate(row, 'target_success_rate')} | {rate(row, 'all_sessions_success_rate')} | "
            f"{rate(row, 'paired_harm_rate')} |"
        )
    lines.extend(
        [
            "",
            "## Selectivity and overhead",
            "",
            "| Arm | Length | Write precision | Write skip rate | Retrieval precision | Retrieval abstention | Retrieval harm | Total tokens | Token delta vs baseline |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in analysis["metrics"]:
        selectivity = row["selectivity"]
        overhead = row["overhead"]

        lines.append(
            f"| {row['arm']} | {row['length']} | {selectivity_value(selectivity, 'write_precision')} | "
            f"{selectivity_value(selectivity, 'write_abstention_rate')} | "
            f"{selectivity_value(selectivity, 'retrieval_precision')} | "
            f"{selectivity_value(selectivity, 'retrieval_abstention_rate')} | "
            f"{selectivity_value(selectivity, 'retrieval_harm_rate')} | "
            f"{overhead_value(overhead, 'total_tokens')} | "
            f"{overhead_value(overhead, 'mean_total_token_delta_vs_baseline')} |"
        )
    lines.extend(["", "## Interpretation", "", analysis["interpretation"], ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--baseline-arm", default="bare")
    args = parser.parse_args()

    analysis = score_sequences(read_jsonl(args.records), baseline_arm=args.baseline_arm)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "sequence_analysis.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out_dir / "sequence_analysis.md").write_text(
        render_markdown(analysis), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
