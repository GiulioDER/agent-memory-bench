"""Analyze the preregistered Code 3 versus Code 4 Task Solve replay.

The analysis is deliberately narrow. It admits only the exact 34 task roster, two frozen replay
arms, and cells retained by the benchmark admission artifact. It then applies the advancement
rule committed in preregistration 091.

    python -m scripts.analyze_code_task_solve --run-id code4-task-solve-001
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from adapters.code_retrieval_replay.adapter import ARM_MODELS, ARMS, EVIDENCE_K
from harness.io import read_jsonl
from harness.memory_startup import TIMEOUT, classify_failure
from harness.schema import SessionRecord

REPO = Path(__file__).resolve().parents[1]
CONTROL, TREATMENT = ARMS

MODIFICATION_TASKS = frozenset(
    {
        "ts-append-only",
        "ts-atomic-write",
        "ts-bool-env",
        "ts-config-layer",
        "ts-crlf-export",
        "ts-golden-regen",
        "ts-ignore-gen",
        "ts-legacy-hash",
        "ts-log-mask",
        "ts-quote-shell",
        "ts-retry-cap",
        "ts-schema-additive",
        "ts-semver-pin",
        "xs-evolve-lease",
    }
)
NEW_ARTIFACT_TASKS = frozenset(
    {
        "fa-dedup-key",
        "ts-base36-id",
        "ts-bom-merge",
        "ts-casefold-sort",
        "ts-cli-exitcode",
        "ts-csv-quote",
        "ts-dedup-order",
        "ts-empty-input",
        "ts-glob-hidden",
        "ts-idempotent-run",
        "ts-json-sorted",
        "ts-manifest-rel",
        "ts-mig-name",
        "ts-natural-order",
        "ts-nfc-count",
        "ts-round-money",
        "ts-stable-sort",
        "ts-tz-utc",
        "xs-join-batch",
        "xs-widen-manifest",
    }
)
ALL_TASKS = MODIFICATION_TASKS | NEW_ARTIFACT_TASKS
MECHANISM_TASKS = frozenset(
    {
        "ts-append-only",
        "ts-crlf-export",
        "ts-golden-regen",
        "ts-mig-name",
        "ts-natural-order",
        "ts-schema-additive",
    }
)


def _mean(values: Iterable[int | float | None]) -> float | None:
    measured = [float(value) for value in values if value is not None]
    return round(statistics.fmean(measured), 4) if measured else None


def _paired(rows: Iterable[tuple[bool, bool]]) -> dict[str, int | float]:
    pairs = list(rows)
    both_success = sum(control and treatment for control, treatment in pairs)
    treatment_only = sum(not control and treatment for control, treatment in pairs)
    control_only = sum(control and not treatment for control, treatment in pairs)
    both_fail = sum(not control and not treatment for control, treatment in pairs)
    total = len(pairs)
    return {
        "paired_cells": total,
        "both_success": both_success,
        "code4_only": treatment_only,
        "code3_only": control_only,
        "both_fail": both_fail,
        "net_wins": treatment_only - control_only,
        "success_rate_difference": round((treatment_only - control_only) / total, 4)
        if total
        else 0.0,
    }


def _failed_tool_calls(record: SessionRecord) -> int:
    return sum(
        bool(call.get("is_error"))
        or bool(call.get("error"))
        or str(call.get("status", "")).lower() in {"error", "failed"}
        for call in record.tool_calls
    )


def _arm_metrics(records: list[SessionRecord]) -> dict[str, Any]:
    kinds = [classify_failure(record)[0] for record in records]
    return {
        "sessions": len(records),
        "successes": sum(record.success for record in records),
        "participant_errors": sum(record.error is not None for record in records),
        "timeouts": sum(kind == TIMEOUT for kind in kinds),
        "failed_tool_calls": sum(_failed_tool_calls(record) for record in records),
        "mean_model_turns": _mean(record.model_turns for record in records),
        "mean_input_tokens": _mean(record.input_tokens for record in records),
        "mean_output_tokens": _mean(record.output_tokens for record in records),
        "mean_wall_time_ms": _mean(record.wall_time_ms for record in records),
        "system_cost_usd": round(sum(record.system_cost_usd or 0 for record in records), 6),
        "evaluator_cost_usd": round(
            sum(record.evaluator_cost_usd or 0 for record in records), 6
        ),
    }


def _diagnostic(record: SessionRecord, artifact_sha256: str) -> Mapping[str, Any]:
    value = record.metadata.get("memory_diagnostic")
    if not isinstance(value, Mapping):
        raise TypeError(f"{record.task_id} seed {record.seed} {record.arm}: missing diagnostic")
    expected = {
        "kind": record.arm,
        "model": ARM_MODELS[record.arm],
        "artifact_sha256": artifact_sha256,
        "task_id": record.task_id,
        "status": "ok",
    }
    for key, wanted in expected.items():
        if value.get(key) != wanted:
            raise ValueError(
                f"{record.task_id} seed {record.seed} {record.arm}: diagnostic {key} mismatch"
            )
    indices = value.get("window_indices")
    paths = value.get("source_paths")
    if not isinstance(indices, list) or len(indices) != EVIDENCE_K or len(set(indices)) != EVIDENCE_K:
        raise ValueError(f"{record.task_id} seed {record.seed} {record.arm}: invalid windows")
    if not isinstance(paths, list) or len(paths) != EVIDENCE_K:
        raise ValueError(f"{record.task_id} seed {record.seed} {record.arm}: invalid sources")
    for key in ("query_sha256", "injected_text_sha256"):
        if not isinstance(value.get(key), str) or len(value[key]) != 64:
            raise ValueError(f"{record.task_id} seed {record.seed} {record.arm}: invalid {key}")
    prompt_hash = record.metadata.get("prompt_sha256")
    if not isinstance(prompt_hash, str) or len(prompt_hash) != 64:
        raise ValueError(f"{record.task_id} seed {record.seed} {record.arm}: invalid prompt hash")
    return value


def analyze(run_dir: Path, *, require_full_roster: bool = True) -> dict[str, Any]:
    records = read_jsonl(run_dir / "records.final.jsonl")
    admission = json.loads((run_dir / "admission.json").read_text(encoding="utf-8"))
    environment = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
    costs = json.loads((run_dir / "costs.json").read_text(encoding="utf-8"))
    if tuple(admission.get("required_arms", ())) != ARMS:
        raise ValueError("admission artifact does not name the frozen replay arms in order")
    if {record.arm for record in records} != set(ARMS):
        raise ValueError("record artifact contains an unexpected arm roster")
    tasks = {record.task_id for record in records}
    if require_full_roster and tasks != ALL_TASKS:
        raise ValueError(
            f"record task roster mismatch: missing={sorted(ALL_TASKS - tasks)}, "
            f"extra={sorted(tasks - ALL_TASKS)}"
        )

    artifact_sha256 = str(environment.get("code_retrieval_artifact_sha256", ""))
    if len(artifact_sha256) != 64:
        raise ValueError("environment artifact has no Code retrieval artifact digest")
    discarded = {tuple(cell) for cell in admission.get("discarded_cells", ())}
    by_cell: dict[tuple[str, int], dict[str, SessionRecord]] = defaultdict(dict)
    all_by_arm = {arm: [] for arm in ARMS}
    evidence: dict[str, dict[str, Any]] = {}
    for record in records:
        key = (record.task_id, record.seed)
        if record.arm in by_cell[key]:
            raise ValueError(f"duplicate record for {key} and {record.arm}")
        by_cell[key][record.arm] = record
        all_by_arm[record.arm].append(record)
        diagnostic = _diagnostic(record, artifact_sha256)
        task_evidence = evidence.setdefault(record.task_id, {})
        existing = task_evidence.get(record.arm)
        identity = {
            "prompt_sha256": record.metadata["prompt_sha256"],
            "query_sha256": diagnostic["query_sha256"],
            "injected_input_tokens": diagnostic.get("injected_input_tokens"),
            "window_indices": diagnostic["window_indices"],
            "source_paths": diagnostic["source_paths"],
        }
        if existing is not None and existing != identity:
            raise ValueError(f"{record.task_id} {record.arm}: replay identity changed across seeds")
        task_evidence[record.arm] = identity

    admitted: dict[tuple[str, int], dict[str, SessionRecord]] = {}
    for cell, arms in by_cell.items():
        if cell in discarded:
            continue
        if set(arms) != set(ARMS):
            raise ValueError(f"admitted cell {cell} is not paired")
        admitted[cell] = arms
    if admission.get("admitted_cells") != len(admitted):
        raise ValueError("admission count does not match the discarded cell set")

    def paired_for(selected: set[str] | frozenset[str]) -> dict[str, int | float]:
        return _paired(
            (arms[CONTROL].success, arms[TREATMENT].success)
            for (task_id, _seed), arms in sorted(admitted.items())
            if task_id in selected
        )

    overall = paired_for(tasks)
    strata = {
        "modification": paired_for(MODIFICATION_TASKS),
        "new_artifact": paired_for(NEW_ARTIFACT_TASKS),
    }
    mechanism = paired_for(MECHANISM_TASKS)
    per_task = {task_id: paired_for({task_id}) for task_id in sorted(tasks)}
    arm_metrics = {arm: _arm_metrics(all_by_arm[arm]) for arm in ARMS}
    for task_id, arms in evidence.items():
        if set(arms) != set(ARMS):
            raise ValueError(f"{task_id}: evidence identity is missing an arm")
        left = set(arms[CONTROL]["source_paths"])
        right = set(arms[TREATMENT]["source_paths"])
        arms["source_path_overlap"] = {
            "intersection": len(left & right),
            "union": len(left | right),
            "jaccard": round(len(left & right) / len(left | right), 4) if left | right else 1.0,
        }

    control_errors = int(arm_metrics[CONTROL]["participant_errors"])
    treatment_errors = int(arm_metrics[TREATMENT]["participant_errors"])
    input_control = arm_metrics[CONTROL]["mean_input_tokens"]
    input_treatment = arm_metrics[TREATMENT]["mean_input_tokens"]
    wall_control = arm_metrics[CONTROL]["mean_wall_time_ms"]
    wall_treatment = arm_metrics[TREATMENT]["mean_wall_time_ms"]
    predictions = {
        "code4_net_wins_at_least_3": overall["net_wins"] >= 3,
        "mechanism_net_wins_at_least_2": mechanism["net_wins"] >= 2,
        "neither_stratum_negative": all(value["net_wins"] >= 0 for value in strata.values()),
        "errors_or_timeouts_within_one": treatment_errors <= control_errors + 1,
        "mean_input_tokens_within_10_percent": bool(
            input_control and input_treatment and abs(input_treatment / input_control - 1) <= 0.10
        ),
        "mean_wall_time_within_20_percent": bool(
            wall_control and wall_treatment and abs(wall_treatment / wall_control - 1) <= 0.20
        ),
    }
    decision_checks = {
        "at_least_90_admitted_cells": len(admitted) >= 90,
        "at_least_3_net_wins": overall["net_wins"] >= 3,
        "neither_stratum_worse_by_more_than_one": all(
            value["net_wins"] >= -1 for value in strata.values()
        ),
        "errors_or_timeouts_within_one": predictions["errors_or_timeouts_within_one"],
    }
    return {
        "schema_version": 1,
        "experiment": "091-voyage-code4-task-solve-replay",
        "run_id": run_dir.name,
        "artifact_sha256": artifact_sha256,
        "admitted_cells": len(admitted),
        "discarded_cells": len(discarded),
        "overall": overall,
        "strata": strata,
        "mechanism_subgroup": mechanism,
        "per_task": per_task,
        "arm_metrics_all_attempted_sessions": arm_metrics,
        "cost_artifact_arms": costs.get("arms", {}),
        "evidence_by_task": dict(sorted(evidence.items())),
        "predictions": predictions,
        "decision_checks": decision_checks,
        "advance_to_official_cambench": all(decision_checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="code4-task-solve-001")
    parser.add_argument("--results-root", type=Path, default=REPO / "results")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    run_dir = args.results_root / args.run_id
    result = analyze(run_dir)
    output = args.out or run_dir / "code4-task-solve-analysis.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **result["decision_checks"]}, indent=2))
    print(f"advance_to_official_cambench={result['advance_to_official_cambench']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
