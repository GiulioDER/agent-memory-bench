"""Analyze RE-call's TS-1 Task Solve replay: the C9 deploy candidate against 091's Code 4 arm.

TS-1 (RE-call's private research record, pre-registered 2026-09-27) runs three replay arms on
091's 34 tasks and seeds: ``code4_replay`` (091's frozen evidence, normalised as in 091),
``c9_norm`` (the candidate's served top 10 through the same normaliser) and ``c9_raw`` (the same
items as served). Admission, pairing and roster rules are 091's; the contrasts and the decision
rule are TS-1's, applied to paired admitted cells.

Amendment A1 (pre-registered 2026-09-27) adds ``c9_raw2`` and ``c9_lw`` to the same run: a second
collect served with LW-1 on, its top 10 alone and its top 10 followed by LW-1's appended windows.
A five-arm run gets TS-1's analysis unchanged plus an ``a1`` section: c9_lw − c9_raw2 (the decision
contrast), c9_raw2 − c9_raw (the rank 9 and 10 draw, reported only), the tasks a majority of
seeds solved under c9_raw2 and failed under c9_lw, the collect's Search p90, and A1's decision.

    python -m scripts.analyze_ts1_task_solve --run-id ts1-001 --served-artifact coding-TS1.json.gz
    python -m scripts.analyze_ts1_task_solve --run-id ts1-001 --served-artifact coding-TS1.json.gz \
        --last-window-artifact coding-TS1-LW.json.gz --last-window-manifest lw-manifest.json
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import statistics
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from adapters.code_retrieval_replay.adapter import ARM_MODELS, CodeRetrievalReplayCatalog
from adapters.code_retrieval_replay.served import (
    LW_ARMS,
    SERVED_ARMS,
    format_served_evidence,
    load_last_window_served,
)
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
TS1_A1_ARMS = (*TS1_ARMS, *LW_ARMS)
#: (treatment, control): A1's decision contrast, then the draw it reports.
A1_CONTRASTS = (("c9_lw", "c9_raw2"), ("c9_raw2", "c9_raw"))
A1_MAX_FLIPS = 2
A1_MAX_P90_MS = 600.0
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


def decide_a1(lw_vs_raw2: float, flips: int, p90_ms: float) -> str:
    """A1's decision rule. ``blocked`` (the gain is there but a guard fails) keeps LW-1 off, as the
    record's "eligible only if" implies; the record does not name that outcome."""
    if lw_vs_raw2 < -0.03:
        return "closed"
    if lw_vs_raw2 < 0.03:
        return "unresolved"
    return "eligible" if flips <= A1_MAX_FLIPS and p90_ms <= A1_MAX_P90_MS else "blocked"


def latency_p90(values: list[float]) -> float:
    """TS-1's p90: the sorted value at index int(0.9 * (n - 1)), which gives its recorded 421 ms."""
    ordered = sorted(values)
    return ordered[int(0.9 * (len(ordered) - 1))]


def majority_flips(cells: list[tuple[str, bool, bool]]) -> list[str]:
    """Tasks a majority of admitted seeds solved under control and a majority failed under treatment.

    ``cells`` is (task, treatment success, control success) per admitted cell; a tie is neither.
    """
    by_task: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    for task_id, treatment, control in cells:
        by_task[task_id].append((treatment, control))
    return sorted(task_id for task_id, pairs in by_task.items()
                  if 2 * sum(c for _, c in pairs) > len(pairs) and 2 * sum(not t for t, _ in pairs) > len(pairs))


def _load_last_window(path: Path, manifest: Path) -> tuple[str, str, dict[str, Any], list[float]]:
    rows = json.loads(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes())["rows"]
    digest, manifest_digest, evidence = load_last_window_served(path, manifest, {str(r["task_id"]) for r in rows})
    return digest, manifest_digest, evidence, [float(r["latency_ms"]) for r in rows]


def _last_window_diagnostics(path: Path, manifest: Path, tasks: set[str]) -> dict[tuple[str, str], dict[str, Any]]:
    catalog = CodeRetrievalReplayCatalog.load(REPLAY_ARTIFACT, REPO / "corpus", last_window_path=path,
                                              last_window_manifest_path=manifest)
    assert catalog.last_window is not None
    out = {}
    for task_id in tasks:
        evidence = catalog.last_window[task_id]
        for arm in LW_ARMS:
            items = evidence.top if arm == "c9_raw2" else (*evidence.top, *evidence.appended)
            text = format_served_evidence(items, normalised=False)
            out[(task_id, arm)] = {
                "kind": arm, "model": ARM_MODELS[arm], "artifact_sha256": catalog.last_window_digest,
                "last_window_manifest_sha256": catalog.last_window_manifest_digest,
                "task_id": task_id, "status": "ok", "query_sha256": catalog.tasks[task_id].query_sha256,
                "item_ids": [i.item_id for i in items], "injected_text_sha256": sha256_text(text),
                "injected_input_tokens": estimated_input_tokens(text),
            }
    return out


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


def analyze(
    run_dir: Path,
    served_path: Path | None = None,
    *,
    require_full_roster: bool = True,
    last_window_path: Path | None = None,
    last_window_manifest_path: Path | None = None,
) -> dict[str, Any]:
    records: list[SessionRecord] = read_jsonl(run_dir / "records.final.jsonl")
    admission = json.loads((run_dir / "admission.json").read_text(encoding="utf-8"))
    environment = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
    run_arms = tuple(admission.get("required_arms", ()))
    if run_arms not in (TS1_ARMS, TS1_A1_ARMS):
        raise ValueError("admission artifact does not name TS-1's arms, or TS-1's and A1's, in order")
    a1 = run_arms == TS1_A1_ARMS
    if {record.arm for record in records} != set(run_arms):
        raise ValueError("record artifact contains an unexpected arm roster")
    tasks = {record.task_id for record in records}
    if require_full_roster and tasks != ALL_TASKS:
        raise ValueError(f"record task roster mismatch: missing={sorted(ALL_TASKS - tasks)}, "
                         f"extra={sorted(tasks - ALL_TASKS)}")
    digests = {"code4_replay": str(environment.get("code_retrieval_artifact_sha256", "")),
               **{arm: str(environment.get("served_evidence_artifact_sha256", "")) for arm in SERVED_ARMS}}
    manifest_digest = ""
    if a1:
        digests.update({arm: str(environment.get("last_window_artifact_sha256", "")) for arm in LW_ARMS})
        manifest_digest = str(environment.get("last_window_manifest_sha256", ""))
        if len(manifest_digest) != 64:
            raise ValueError("environment artifact lacks the last-window manifest digest")
        if last_window_path is None or last_window_manifest_path is None:
            raise ValueError("an A1 run needs the last-window artifact and manifest (for its Search p90)")
        lw_digest, lw_manifest_digest, lw_evidence, lw_latencies = _load_last_window(
            last_window_path, last_window_manifest_path)
        if (lw_digest, lw_manifest_digest) != (digests["c9_lw"], manifest_digest):
            raise ValueError("the last-window files given are not the ones the run used")
    if any(len(value) != 64 for value in digests.values()):
        raise ValueError("environment artifact lacks an evidence digest")
    missing = any(not isinstance(r.metadata.get("memory_diagnostic"), Mapping) for r in records)
    reconstructed: dict[tuple[str, str], Mapping[str, Any]] = {}
    if missing:
        if served_path is None:
            raise ValueError("diagnostics are missing from the records; pass the served artifact to rebuild them")
        reconstructed.update(_artifact_diagnostics(digests["code4_replay"], tasks))
        reconstructed.update(_served_diagnostics(served_path, tasks))
        if a1:
            assert last_window_path is not None and last_window_manifest_path is not None
            reconstructed.update(_last_window_diagnostics(last_window_path, last_window_manifest_path, tasks))

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
        if record.arm in LW_ARMS and diagnostic.get("last_window_manifest_sha256") != manifest_digest:
            raise ValueError(f"{record.task_id} seed {record.seed} {record.arm}: diagnostic manifest mismatch")
        injected = str(diagnostic.get("injected_text_sha256", ""))
        previous = identity.setdefault((record.task_id, record.arm), injected)
        if previous != injected:
            raise ValueError(f"{record.task_id} {record.arm}: evidence changed across seeds")

    discarded = {tuple(cell) for cell in admission.get("discarded_cells", ())}
    admitted = {}
    for cell, arms in by_cell.items():
        if cell in discarded:
            continue
        if set(arms) != set(run_arms):
            raise ValueError(f"admitted cell {cell} is not complete across the run's arms")
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
             if admitted else None for arm in run_arms}
    norm_vs_code4 = contrasts["c9_norm_minus_code4_replay"]["all"]["difference"]
    raw_vs_norm = contrasts["c9_raw_minus_c9_norm"]["all"]["difference"]
    result: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "re-call-ts1-deploy-candidate-task-solve",
        "run_id": run_dir.name,
        "artifact_sha256": digests,
        "admitted_cells": len(admitted),
        "discarded_cells": len(discarded),
        "success_rates": rates,
        "contrasts": contrasts,
        "arm_metrics_all_attempted_sessions": {
            arm: _arm_metrics([r for r in records if r.arm == arm]) for arm in run_arms},
        "predictions": {
            "code4_rate_in_0.57_to_0.77": rates["code4_replay"] is not None and 0.57 <= rates["code4_replay"] <= 0.77,
            "norm_minus_code4_in_-0.06_to_0.06": -0.06 <= norm_vs_code4 <= 0.06,
            "raw_minus_norm_in_0.00_to_0.12": 0.0 <= raw_vs_norm <= 0.12,
        },
        "decision": decide(norm_vs_code4, raw_vs_norm),
    }
    if a1:
        a1_contrasts = {f"{t}_minus_{c}": {"all": contrast(t, c, tasks),
                                            "modification": contrast(t, c, MODIFICATION_TASKS & tasks),
                                            "new_artifact": contrast(t, c, NEW_ARTIFACT_TASKS & tasks)}
                        for t, c in A1_CONTRASTS}
        lw_vs_raw2 = a1_contrasts["c9_lw_minus_c9_raw2"]["all"]["difference"]
        raw2_vs_raw = a1_contrasts["c9_raw2_minus_c9_raw"]["all"]["difference"]
        flips = majority_flips([(task_id, arms["c9_lw"].success, arms["c9_raw2"].success)
                                for (task_id, _seed), arms in sorted(admitted.items())])
        appended = [len(evidence.appended) for evidence in lw_evidence.values()]
        p90 = latency_p90(lw_latencies)
        result["a1"] = {
            "contrasts": a1_contrasts,
            "raw2_solved_lw_failed_tasks": flips,
            "appended_median": statistics.median(appended),
            "appended_max": max(appended),
            "search_p90_ms": p90,
            "predictions": {
                "lw_minus_raw2_in_0.00_to_0.10": 0.0 <= lw_vs_raw2 <= 0.10,
                "raw2_minus_raw_in_-0.05_to_0.05": -0.05 <= raw2_vs_raw <= 0.05,
                "appended_median_in_2_to_4": 2 <= statistics.median(appended) <= 4,
                "appended_max_at_most_6": max(appended) <= 6,
                "search_p90_at_most_600_ms": p90 <= A1_MAX_P90_MS,
            },
            "decision": decide_a1(lw_vs_raw2, len(flips), p90),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-root", type=Path, default=REPO / "results")
    parser.add_argument("--served-artifact", type=Path)
    parser.add_argument("--last-window-artifact", type=Path, help="A1's LW-1 collect (five-arm runs)")
    parser.add_argument("--last-window-manifest", type=Path, help="A1's apparatus manifest (five-arm runs)")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    run_dir = args.results_root / args.run_id
    result = analyze(run_dir, args.served_artifact, last_window_path=args.last_window_artifact,
                     last_window_manifest_path=args.last_window_manifest)
    output = args.out or run_dir / "ts1-analysis.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "decision": result["decision"],
                      "a1_decision": result.get("a1", {}).get("decision"),
                      "success_rates": result["success_rates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
