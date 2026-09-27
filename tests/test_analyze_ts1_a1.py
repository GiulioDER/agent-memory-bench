"""TS-1 amendment A1 in the analyzer: c9_lw − c9_raw2 decides, under two guards, on paired admitted cells.

Invariants: A1's decision is ``closed`` below −0.03, ``unresolved`` from −0.03 up to +0.03, and at
+0.03 or more ``eligible`` only with at most 2 tasks solved by a majority of seeds under c9_raw2 and
failed by a majority under c9_lw and a Search p90 of at most 600 ms, else ``blocked``; a tie of
seeds is neither solved nor failed; a five-arm run keeps TS-1's own analysis and adds ``a1``; the
last-window files given must be the ones the run recorded, and every A1 record must name the same
manifest.

Red proof, 2026-09-27, each against ``scripts/analyze_ts1_task_solve.py`` with this file unchanged
(``PYTHONDONTWRITEBYTECODE=1``):
- ``decide_a1`` with ``<= 0.03`` for unresolved: ``test_the_a1_decision_rule`` fails at
  ``== "eligible"``.
- ``majority_flips`` with ``>=`` for a majority: ``test_a_tie_of_seeds_is_not_a_flip`` fails at
  ``== []``.
- A1's ``"all"`` contrast called as ``contrast(c, t, tasks)`` (control minus treatment):
  ``test_a_five_arm_run_adds_a1_to_ts1s_analysis`` fails at its first ``difference`` assertion.
- the given-files digest comparison removed: ``test_last_window_files_the_run_did_not_use_are_refused``
  fails at ``DID NOT RAISE``.
- the per-record manifest comparison removed: ``test_a_record_naming_another_manifest_is_refused``
  fails at ``DID NOT RAISE``.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from adapters.code_retrieval_replay.served import LW_MANIFEST_SCHEMA
from scripts.analyze_ts1_task_solve import TS1_A1_ARMS, analyze, decide_a1, majority_flips

CODE4, SERVED = hashlib.sha256(b"091").hexdigest(), hashlib.sha256(b"served").hexdigest()
TASK = "ts-bool-env"
MODELS = {"code4_replay": "voyage-code-4", "c9_norm": "re-call-c9-deploy-candidate",
          "c9_raw": "re-call-c9-deploy-candidate", "c9_raw2": "re-call-c9-last-window",
          "c9_lw": "re-call-c9-last-window"}


def _lw_files(root: Path, latencies=(300.0, 350.0, 700.0)) -> tuple[Path, Path, str, str]:
    """One task's LW-1 collect (ten items, two appended) and its manifest; plus both digests."""
    items = [{"id": f"i{n}", "kind": "raw", "session_id": "s", "created_at": "", "content": f"w{n}"} for n in range(10)]
    items += [{"id": f"last-{n}", "kind": "raw", "session_id": f"s{n}", "created_at": "", "content": f"last {n}"}
              for n in range(2)]
    rows = [{"task_id": TASK, "status": 200, "latency_ms": latencies[0], "top_items": items}]
    rows += [{"task_id": f"other-{n}", "status": 200, "latency_ms": value, "top_items": items[:10]}
             for n, value in enumerate(latencies[1:])]
    artifact = root / "lw.json.gz"
    artifact.write_bytes(gzip.compress(json.dumps({"rows": rows}).encode()))
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = root / "lw-manifest.json"
    tasks = {row["task_id"]: [] for row in rows} | {TASK: ["last-0", "last-1"]}
    manifest.write_text(json.dumps({"schema": LW_MANIFEST_SCHEMA, "served_sha256": digest, "tasks": tasks}),
                        encoding="utf-8")
    return artifact, manifest, digest, hashlib.sha256(manifest.read_bytes()).hexdigest()


def _write_run(root: Path, outcomes: dict[tuple[str, int, str], bool], lw_digest: str, manifest_digest: str) -> Path:
    run = root / "ts1-a1-test"
    run.mkdir()
    digest = {"code4_replay": CODE4, "c9_norm": SERVED, "c9_raw": SERVED, "c9_raw2": lw_digest, "c9_lw": lw_digest}
    records = []
    for (task, seed, arm), ok in outcomes.items():
        diagnostic = {"kind": arm, "model": MODELS[arm], "task_id": task, "status": "ok",
                      "artifact_sha256": digest[arm],
                      "injected_text_sha256": hashlib.sha256(f"{task}{arm}".encode()).hexdigest()}
        if arm in ("c9_raw2", "c9_lw"):
            diagnostic["last_window_manifest_sha256"] = manifest_digest
        records.append({"task_id": task, "seed": seed, "arm": arm, "success": ok, "input_tokens": 100,
                        "output_tokens": 10, "model_turns": 2, "wall_time_ms": 1000,
                        "metadata": {"prompt_sha256": "0" * 64, "memory_diagnostic": diagnostic}})
    (run / "records.final.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    cells = {(t, s) for t, s, _ in outcomes}
    (run / "admission.json").write_text(json.dumps({"required_arms": list(TS1_A1_ARMS), "admitted_cells": len(cells),
                                                    "discarded_cells": []}), encoding="utf-8")
    (run / "environment.json").write_text(json.dumps({
        "code_retrieval_artifact_sha256": CODE4, "served_evidence_artifact_sha256": SERVED,
        "last_window_artifact_sha256": lw_digest, "last_window_manifest_sha256": manifest_digest,
    }), encoding="utf-8")
    return run


def _grid(lw: list[bool], raw2: list[bool]) -> dict:
    return {(TASK, seed, arm): (lw[seed] if arm == "c9_lw" else raw2[seed] if arm == "c9_raw2" else False)
            for seed in range(len(lw)) for arm in TS1_A1_ARMS}


def _analyze(tmp_path: Path, outcomes: dict, **files):
    artifact, manifest, lw_digest, manifest_digest = _lw_files(tmp_path)
    run = _write_run(tmp_path, outcomes, lw_digest, manifest_digest)
    return analyze(run, require_full_roster=False, last_window_path=files.get("artifact", artifact),
                   last_window_manifest_path=files.get("manifest", manifest))


def test_the_a1_decision_rule() -> None:
    assert decide_a1(0.03, 2, 600.0) == "eligible"
    assert decide_a1(0.029, 0, 100.0) == "unresolved"
    assert decide_a1(-0.03, 0, 100.0) == "unresolved"
    assert decide_a1(-0.031, 0, 100.0) == "closed"
    assert decide_a1(0.2, 3, 100.0) == "blocked"
    assert decide_a1(0.2, 0, 600.1) == "blocked"


def test_a_tie_of_seeds_is_not_a_flip() -> None:
    assert majority_flips([("t", False, True), ("t", False, True), ("t", True, False)]) == ["t"]
    assert majority_flips([("t", False, True), ("t", True, False)]) == []


def test_a_five_arm_run_adds_a1_to_ts1s_analysis(tmp_path: Path) -> None:
    result = _analyze(tmp_path, _grid(lw=[True, True, False], raw2=[False, True, False]))

    a1 = result["a1"]
    assert a1["contrasts"]["c9_lw_minus_c9_raw2"]["all"]["difference"] == pytest.approx(1 / 3, abs=1e-4)
    assert a1["contrasts"]["c9_raw2_minus_c9_raw"]["all"]["difference"] == pytest.approx(1 / 3, abs=1e-4)
    assert a1["raw2_solved_lw_failed_tasks"] == []
    assert (a1["appended_median"], a1["appended_max"]) == (0, 2)
    assert a1["search_p90_ms"] == 350.0
    assert a1["decision"] == "eligible"
    assert result["decision"] in {"pass", "fail", "inconclusive"}
    assert set(result["success_rates"]) == set(TS1_A1_ARMS)


def test_last_window_files_the_run_did_not_use_are_refused(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    artifact, manifest, _, _ = _lw_files(other, latencies=(300.0, 351.0, 700.0))
    with pytest.raises(ValueError, match="not the ones the run used"):
        _analyze(tmp_path, _grid(lw=[True], raw2=[False]), artifact=artifact, manifest=manifest)


def test_a_record_naming_another_manifest_is_refused(tmp_path: Path) -> None:
    artifact, manifest, lw_digest, manifest_digest = _lw_files(tmp_path)
    run = _write_run(tmp_path, _grid(lw=[True], raw2=[False]), lw_digest, manifest_digest)
    rows = [json.loads(line) for line in (run / "records.final.jsonl").read_text().split("\n") if line]
    rows[-1]["metadata"]["memory_diagnostic"]["last_window_manifest_sha256"] = "0" * 64
    (run / "records.final.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest mismatch"):
        analyze(run, require_full_roster=False, last_window_path=artifact, last_window_manifest_path=manifest)
