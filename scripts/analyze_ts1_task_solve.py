"""Analyze RE-call's TS-1 Task Solve replay: the C9 deploy candidate against 091's Code 4 arm.

TS-1 (RE-call's private research record, pre-registered 2026-09-27) runs three replay arms on
091's 34 tasks and seeds: ``code4_replay`` (091's frozen evidence, normalised as in 091),
``c9_norm`` (the candidate's served top 10 through the same normaliser) and ``c9_raw`` (the same
items as served). Admission, pairing and roster rules are 091's; the contrasts and the decision
rule are TS-1's, applied to paired admitted cells.

    python -m scripts.analyze_ts1_task_solve --run-id ts1-001 --served-artifact coding-TS1.json.gz
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from adapters.code_retrieval_replay.adapter import ARM_MODELS, CodeRetrievalReplayCatalog
from adapters.code_retrieval_replay.served import SERVED_ARMS, format_served_evidence
from harness.io import read_jsonl
from harness.memory_prompt import estimated_input_tokens, sha256_text
from harness.schema import SessionRecord
from scripts.analyze_code_task_solve import (
    ALL_TASKS,
    MODIFICATION_TASKS,
    NEW_ARTIFACT_TASKS,
    REPLAY_ARTIFACT,
    REPO,
    _arm_metrics,
    _artifact_diagnostics,
)

TS1_ARMS = ("code4_replay", "c9_norm", "c9_raw")
#: (treatment, control): the pre-registered contrasts, in the record's order.
CONTRASTS = (("c9_norm", "code4_replay"), ("c9_raw", "c9_norm"), ("c9_raw", "code4_replay"))
SEED = 20260927


def paired(pairs: list[tuple[bool, bool]]) -> dict[str, Any]:
    """Treatment minus control on paired admitted cells, with a paired bootstrap interval."""
    n = len(pairs)
    diffs = [int(t) - int(c) for t, c in pairs]
    rng = random.Random(SEED)
    boots = sorted(sum(rng.choices(diffs, k=n)) / n for _ in range(10_000)) if n else [0.0]
    return {
        "paired_cells": n,
        "treatment_rate": round(sum(t for t, _ in pairs) / n, 4) if n else None,
        "control_rate": round(sum(c for _, c in pairs) / n, 4) if n else None,
        "treatment_only": sum(t and not c for t, c in pairs),
        "control_only": sum(c and not t for t, c in pairs),
        "difference": round(sum(diffs) / n, 4) if n else 0.0,
        "ci95": [round(boots[249], 4), round(boots[9_749], 4)] if n else [0.0, 0.0],
    }


def decide(norm_vs_code4: float, raw_vs_norm: float) -> str:
    """TS-1's decision rule: pass, fail, or neither."""
    if norm_vs_code4 < -0.08:
        return "fail"
    if norm_vs_code4 >= -0.05 and raw_vs_norm >= -0.05:
        return "pass"
    return "inconclusive"


def _served_diagnostics(served_path: Path, tasks: set[str]) -> dict[tuple[str, str], dict[str, Any]]:
    catalog = CodeRetrievalReplayCatalog.load(REPLAY_ARTIFACT, REPO / "corpus", served_path=served_path)
    assert catalog.served is not None
    out = {}
    for task_id in tasks:
        items = catalog.served[task_id]
        for arm in SERVED_ARMS:
            text = format_served_evidence(items, normalised=arm == "c9_norm")
            out[(task_id, arm)] = {
                "kind": arm, "model": ARM_MODELS[arm], "artifact_sha256": catalog.served_digest,
                "task_id": task_id, "status": "ok", "query_sha256": catalog.tasks[task_id].query_sha256,
                "item_ids": [i.item_id for i in items], "injected_text_sha256": sha256_text(text),
                "injected_input_tokens": estimated_input_tokens(text),
            }
    return out


def analyze(run_dir: Path, served_path: Path | None = None, *, require_full_roster: bool = True) -> dict[str, Any]:
    records: list[SessionRecord] = read_jsonl(run_dir / "records.final.jsonl")
    admission = json.loads((run_dir / "admission.json").read_text(encoding="utf-8"))
    environment = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
    if tuple(admission.get("required_arms", ())) != TS1_ARMS:
        raise ValueError("admission artifact does not name TS-1's arms in order")
    if {record.arm for record in records} != set(TS1_ARMS):
        raise ValueError("record artifact contains an unexpected arm roster")
    tasks = {record.task_id for record in records}
    if require_full_roster and tasks != ALL_TASKS:
        raise ValueError(f"record task roster mismatch: missing={sorted(ALL_TASKS - tasks)}, "
                         f"extra={sorted(tasks - ALL_TASKS)}")
    digests = {"code4_replay": str(environment.get("code_retrieval_artifact_sha256", "")),
               **{arm: str(environment.get("served_evidence_artifact_sha256", "")) for arm in SERVED_ARMS}}
    if any(len(value) != 64 for value in digests.values()):
        raise ValueError("environment artifact lacks an evidence digest")
    missing = any(not isinstance(r.metadata.get("memory_diagnostic"), Mapping) for r in records)
    reconstructed: dict[tuple[str, str], Mapping[str, Any]] = {}
    if missing:
        if served_path is None:
            raise ValueError("diagnostics are missing from the records; pass the served artifact to rebuild them")
        reconstructed.update(_artifact_diagnostics(digests["code4_replay"], tasks))
        reconstructed.update(_served_diagnostics(served_path, tasks))

    by_cell: dict[tuple[str, int], dict[str, SessionRecord]] = defaultdict(dict)
    identity: dict[tuple[str, str], str] = {}
    for record in records:
        key = (record.task_id, record.seed)
        if record.arm in by_cell[key]:
            raise ValueError(f"duplicate record for {key} and {record.arm}")
        by_cell[key][record.arm] = record
        diagnostic = record.metadata.get("memory_diagnostic")
        if not isinstance(diagnostic, Mapping):
            diagnostic = reconstructed.get((record.task_id, record.arm))
        if not isinstance(diagnostic, Mapping):
            raise TypeError(f"{record.task_id} seed {record.seed} {record.arm}: missing diagnostic")
        for field, wanted in (("kind", record.arm), ("model", ARM_MODELS[record.arm]),
                              ("artifact_sha256", digests[record.arm]), ("task_id", record.task_id),
                              ("status", "ok")):
            if diagnostic.get(field) != wanted:
                raise ValueError(f"{record.task_id} seed {record.seed} {record.arm}: diagnostic {field} mismatch")
        injected = str(diagnostic.get("injected_text_sha256", ""))
        previous = identity.setdefault((record.task_id, record.arm), injected)
        if previous != injected:
            raise ValueError(f"{record.task_id} {record.arm}: evidence changed across seeds")

    discarded = {tuple(cell) for cell in admission.get("discarded_cells", ())}
    admitted = {}
    for cell, arms in by_cell.items():
        if cell in discarded:
            continue
        if set(arms) != set(TS1_ARMS):
            raise ValueError(f"admitted cell {cell} is not complete across TS-1's arms")
        admitted[cell] = arms
    if admission.get("admitted_cells") != len(admitted):
        raise ValueError("admission count does not match the discarded cell set")

    def contrast(treatment: str, control: str, selected: set[str] | frozenset[str]) -> dict[str, Any]:
        return paired([(arms[treatment].success, arms[control].success)
                       for (task_id, _seed), arms in sorted(admitted.items()) if task_id in selected])

    contrasts = {f"{t}_minus_{c}": {"all": contrast(t, c, tasks),
                                     "modification": contrast(t, c, MODIFICATION_TASKS & tasks),
                                     "new_artifact": contrast(t, c, NEW_ARTIFACT_TASKS & tasks)}
                 for t, c in CONTRASTS}
    rates = {arm: round(sum(arms[arm].success for arms in admitted.values()) / len(admitted), 4)
             if admitted else None for arm in TS1_ARMS}
    norm_vs_code4 = contrasts["c9_norm_minus_code4_replay"]["all"]["difference"]
    raw_vs_norm = contrasts["c9_raw_minus_c9_norm"]["all"]["difference"]
    return {
        "schema_version": 1,
        "experiment": "re-call-ts1-deploy-candidate-task-solve",
        "run_id": run_dir.name,
        "artifact_sha256": digests,
        "admitted_cells": len(admitted),
        "discarded_cells": len(discarded),
        "success_rates": rates,
        "contrasts": contrasts,
        "arm_metrics_all_attempted_sessions": {
            arm: _arm_metrics([r for r in records if r.arm == arm]) for arm in TS1_ARMS},
        "predictions": {
            "code4_rate_in_0.57_to_0.77": rates["code4_replay"] is not None and 0.57 <= rates["code4_replay"] <= 0.77,
            "norm_minus_code4_in_-0.06_to_0.06": -0.06 <= norm_vs_code4 <= 0.06,
            "raw_minus_norm_in_0.00_to_0.12": 0.0 <= raw_vs_norm <= 0.12,
        },
        "decision": decide(norm_vs_code4, raw_vs_norm),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-root", type=Path, default=REPO / "results")
    parser.add_argument("--served-artifact", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    run_dir = args.results_root / args.run_id
    result = analyze(run_dir, args.served_artifact)
    output = args.out or run_dir / "ts1-analysis.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "decision": result["decision"],
                      "success_rates": result["success_rates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
