"""Render machine readable and Markdown analysis for the four arm diagnostic."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from harness.io import read_jsonl

ARMS = ("claude_md", "recall", "oracle_memory", "recall_prefetch")


def _cluster_ci(deltas: list[float], *, seed: int = 20260825, draws: int = 10000) -> list[float] | None:
    if len(deltas) < 2 or len(set(deltas)) == 1:
        return None
    rng = random.Random(seed)
    samples = sorted(sum(deltas[rng.randrange(len(deltas))] for _ in deltas) / len(deltas) for _ in range(draws))
    return [samples[int(draws * 0.025)], samples[int(draws * 0.975)]]


def compare(records, higher_is_better: bool = True) -> dict:
    by_cell = {(record.task_id, record.seed, record.arm): record for record in records}
    tasks = sorted({record.task_id for record in records})
    per_task = []
    for task in tasks:
        baseline = [by_cell[(task, seed, "claude_md")].success for seed in sorted({record.seed for record in records if record.task_id == task}) if (task, seed, "claude_md") in by_cell]
        if not baseline:
            continue
        row = {"task_id": task, "baseline_rate": sum(baseline) / len(baseline), "arms": {}}
        for arm in ARMS[1:]:
            values = [by_cell[(task, seed, arm)].success for seed in sorted({record.seed for record in records if record.task_id == task}) if (task, seed, arm) in by_cell]
            row["arms"][arm] = {"rate": sum(values) / len(values) if values else None, "delta": (sum(values) / len(values) - row["baseline_rate"]) if values else None}
        per_task.append(row)
    summary = {}
    for arm in ARMS:
        values = [record.success for record in records if record.arm == arm]
        summary[arm] = {"successes": sum(values), "n": len(values), "rate": sum(values) / len(values) if values else None}
    contrasts = {}
    for arm, name in (("oracle_memory", "oracle_headroom"), ("recall", "natural_memory_lift"), ("recall_prefetch", "prefetch_memory_lift")):
        deltas = []
        for row in per_task:
            value = row["arms"][arm]["delta"]
            if value is not None:
                deltas.append(value)
        contrasts[name] = {"mean_delta": sum(deltas) / len(deltas) if deltas else None, "cluster_ci": _cluster_ci(deltas), "n_tasks": len(deltas)}
    oracle_by_task = {row["task_id"]: row["arms"]["oracle_memory"]["delta"] for row in per_task}
    contrasts["access_gap"] = {
        "mean_delta": (sum((row["arms"]["oracle_memory"]["rate"] or 0) - (row["arms"]["recall"]["rate"] or 0) for row in per_task) / len(per_task)) if per_task else None,
        "cluster_ci": _cluster_ci([(row["arms"]["oracle_memory"]["rate"] or 0) - (row["arms"]["recall"]["rate"] or 0) for row in per_task]) if per_task else None,
    }
    contrasts["prefetch_gap"] = {
        "mean_delta": (sum((row["arms"]["recall_prefetch"]["rate"] or 0) - (row["arms"]["recall"]["rate"] or 0) for row in per_task) / len(per_task)) if per_task else None,
        "cluster_ci": _cluster_ci([(row["arms"]["recall_prefetch"]["rate"] or 0) - (row["arms"]["recall"]["rate"] or 0) for row in per_task]) if per_task else None,
    }
    diagnostic_records = [record for record in records if isinstance(record.metadata.get("memory_diagnostic"), dict)]
    natural = [record for record in records if record.arm == "recall"]
    return {
        "arms": summary,
        "contrasts": contrasts,
        "per_task": per_task,
        "mechanism": {
            "natural_search_rate": (sum(record.memory_call_count > 0 for record in natural) / len(natural)) if natural else None,
            "oracle_supplied_records": sum(record.arm == "oracle_memory" for record in diagnostic_records),
            "prefetch_successful_records": sum(record.arm == "recall_prefetch" and record.metadata.get("memory_diagnostic", {}).get("prefetch_status") == "ok" for record in diagnostic_records),
            "prefetch_abstentions": sum(record.metadata.get("memory_diagnostic", {}).get("abstained") is True for record in diagnostic_records if record.arm == "recall_prefetch"),
        },
        "no_measurable_headroom_tasks": sorted(task for task, delta in oracle_by_task.items() if delta is not None and delta <= 0),
        "negative_transfer_tasks": sorted(task for task, row in ((row["task_id"], row) for row in per_task) if any((value["delta"] is not None and value["delta"] < 0) for value in row["arms"].values())),
        "interpretation": "Diagnostic arms are reference tracks and are not combined into a product ranking. Gaps are descriptive unless the preregistration states otherwise.",
    }


def render_markdown(analysis: dict) -> str:
    lines = ["# Oracle and Prefetch Diagnostic", "", "Diagnostic arms are reference tracks, not ranked products.", "", "## Success rates", "", "| Arm | Successes | N | Rate |", "|---|---:|---:|---:|"]
    for arm in ARMS:
        row = analysis["arms"][arm]
        rate = "unknown" if row["rate"] is None else f"{row['rate']:.3f}"
        lines.append(f"| {arm} | {row['successes']} | {row['n']} | {rate} |")
    lines.extend(["", "## Primary contrasts", "", "| Contrast | Mean delta | Cluster interval |", "|---|---:|---|"])
    for name in ("oracle_headroom", "natural_memory_lift", "prefetch_memory_lift", "access_gap", "prefetch_gap"):
        row = analysis["contrasts"].get(name, {})
        delta = "unknown" if row.get("mean_delta") is None else f"{row['mean_delta']:.3f}"
        ci = row.get("cluster_ci")
        interval = "unknown" if ci is None else f"[{ci[0]:.3f}, {ci[1]:.3f}]"
        lines.append(f"| {name} | {delta} | {interval} |")
    lines.extend(["", "## Interpretation", "", analysis["interpretation"], "", "## Tasks with no measurable oracle headroom", ""])
    lines.extend(f"* {task}" for task in analysis["no_measurable_headroom_tasks"] or ["None recorded."])
    lines.extend(["", "## Negative transfer", ""])
    lines.extend(f"* {task}" for task in analysis["negative_transfer_tasks"] or ["None recorded."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("records", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    analysis = compare(read_jsonl(args.records))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "diagnostic_analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out_dir / "diagnostic_analysis.md").write_text(render_markdown(analysis), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
