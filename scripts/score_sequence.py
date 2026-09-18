"""Score longitudinal chains from a records.final.jsonl artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness.io import read_jsonl
from harness.sequence import score_sequences
from harness.sequence_labels import apply_label_set, load_label_set_file
from harness.sequence_plan import load_plan_file


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
        "| Arm | Length | Write precision | Write skip rate | Useful write skips | Retrieval precision | Retrieval abstention | Useful retrieval abstentions | Retrieval harm | Total tokens | Token delta vs baseline | Tool calls | Tool-call delta vs baseline | Wall time (ms) | Wall-time delta vs baseline |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in analysis["metrics"]:
        selectivity = row["selectivity"]
        overhead = row["overhead"]

        lines.append(
            f"| {row['arm']} | {row['length']} | {selectivity_value(selectivity, 'write_precision')} | "
            f"{selectivity_value(selectivity, 'write_abstention_rate')} | "
            f"{selectivity_value(selectivity, 'write_useful_abstention_rate')} | "
            f"{selectivity_value(selectivity, 'retrieval_precision')} | "
            f"{selectivity_value(selectivity, 'retrieval_abstention_rate')} | "
            f"{selectivity_value(selectivity, 'retrieval_useful_abstention_rate')} | "
            f"{selectivity_value(selectivity, 'retrieval_harm_rate')} | "
            f"{overhead_value(overhead, 'total_tokens')} | "
            f"{overhead_value(overhead, 'mean_total_token_delta_vs_baseline')} | "
            f"{overhead_value(overhead, 'tool_calls')} | "
            f"{overhead_value(overhead, 'mean_tool_call_delta_vs_baseline')} | "
            f"{overhead_value(overhead, 'wall_time_ms')} | "
            f"{overhead_value(overhead, 'mean_wall_time_delta_vs_baseline')} |"
        )
    lines.extend(["", "## Interpretation", "", analysis["interpretation"], ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--baseline-arm", default="bare")
    parser.add_argument(
        "--oracle-labels",
        type=Path,
        help="post run oracle label artifact; requires --sequence-plan",
    )
    parser.add_argument(
        "--sequence-plan",
        type=Path,
        help="sequence plan used to bind an oracle label artifact",
    )
    args = parser.parse_args()

    records = read_jsonl(args.records)
    if args.oracle_labels:
        if not args.sequence_plan:
            parser.error("--oracle-labels requires --sequence-plan")
        plan = load_plan_file(args.sequence_plan)
        label_set = load_label_set_file(args.oracle_labels)
        if (
            label_set.sequence_plan_id != plan.plan_id
            or label_set.sequence_plan_digest != plan.digest
            or label_set.evaluation_manifest_id != plan.evaluation_manifest_id
            or label_set.evaluation_manifest_digest != plan.evaluation_manifest_digest
        ):
            parser.error("oracle labels are bound to a different sequence plan or held out manifest")
        records = list(apply_label_set(records, label_set))
    analysis = score_sequences(records, baseline_arm=args.baseline_arm)
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
