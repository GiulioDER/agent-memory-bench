"""TS-1's analyzer applies the pre-registered contrasts and decision rule to admitted cells.

Invariants: a contrast is treatment minus control over paired admitted cells; a discarded cell is
left out; a cell missing one of the three arms, evidence that changes across seeds, or a record
naming the wrong evidence artifact stops the analysis; the decision is ``pass`` when c9_norm is no
more than 0.05 below code4_replay and c9_raw no more than 0.05 below c9_norm, ``fail`` when c9_norm
is more than 0.08 below code4_replay, and ``inconclusive`` otherwise.

Red proof, 2026-09-27, each against ``scripts/analyze_ts1_task_solve.py`` with this file unchanged
(``PYTHONDONTWRITEBYTECODE=1``):
- ``decide`` with ``> -0.05`` for the pass threshold: ``test_the_decision_rule`` fails at ``== "pass"``.
- ``contrast`` pairing (control, treatment): ``test_a_contrast_is_treatment_minus_control``
  fails at ``== 0.5``.
- the complete-cell check removed: ``test_an_incomplete_cell_stops_the_analysis`` fails at
  ``"not complete" in``, the analysis crashing later on a ``KeyError`` instead of refusing clearly.
- the across-seeds identity check removed: ``test_evidence_changing_across_seeds_stops_it`` fails at
  ``DID NOT RAISE``.
- the discarded-cell skip removed together with the admission-count check that would otherwise
  catch it first: ``test_a_discarded_cell_is_left_out`` fails at ``== 1``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.analyze_ts1_task_solve import TS1_ARMS, analyze, decide

CODE4, SERVED = hashlib.sha256(b"091").hexdigest(), hashlib.sha256(b"served").hexdigest()
MODELS = {"code4_replay": "voyage-code-4", "c9_norm": "re-call-c9-deploy-candidate",
          "c9_raw": "re-call-c9-deploy-candidate"}


def _write_run(root: Path, outcomes: dict[tuple[str, int, str], bool], discarded=()) -> Path:
    run = root / "ts1-test"
    run.mkdir()
    records = [{
        "task_id": task, "seed": seed, "arm": arm, "success": ok, "input_tokens": 100, "output_tokens": 10,
        "model_turns": 2, "wall_time_ms": 1000,
        "metadata": {"prompt_sha256": hashlib.sha256(f"{task}{arm}".encode()).hexdigest(),
                     "memory_diagnostic": {"kind": arm, "model": MODELS[arm], "task_id": task, "status": "ok",
                                           "artifact_sha256": CODE4 if arm == "code4_replay" else SERVED,
                                           "injected_text_sha256": hashlib.sha256(f"{task}{arm}".encode()).hexdigest()}},
    } for (task, seed, arm), ok in outcomes.items()]
    (run / "records.final.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    cells = {(t, s) for t, s, _ in outcomes} - {tuple(c) for c in discarded}
    (run / "admission.json").write_text(json.dumps({"required_arms": list(TS1_ARMS), "admitted_cells": len(cells),
                                                    "discarded_cells": [list(c) for c in discarded]}), encoding="utf-8")
    (run / "environment.json").write_text(json.dumps({"code_retrieval_artifact_sha256": CODE4,
                                                      "served_evidence_artifact_sha256": SERVED}), encoding="utf-8")
    (run / "costs.json").write_text(json.dumps({"arms": {}}), encoding="utf-8")
    return run


def _grid(norm: list[bool], task: str = "ts-bool-env") -> dict:
    return {(task, seed, arm): (norm[seed] if arm == "c9_norm" else False)
            for seed in range(len(norm)) for arm in TS1_ARMS}


def test_the_decision_rule() -> None:
    assert decide(-0.05, -0.05) == "pass"
    assert decide(-0.06, 0.0) == "inconclusive"
    assert decide(0.0, -0.06) == "inconclusive"
    assert decide(-0.09, 0.2) == "fail"


def test_a_contrast_is_treatment_minus_control(tmp_path: Path) -> None:
    result = analyze(_write_run(tmp_path, _grid([True, False])), require_full_roster=False)
    assert result["contrasts"]["c9_norm_minus_code4_replay"]["all"]["difference"] == 0.5
    assert result["contrasts"]["c9_raw_minus_c9_norm"]["all"]["difference"] == -0.5


def test_a_discarded_cell_is_left_out(tmp_path: Path) -> None:
    run = _write_run(tmp_path, _grid([True, False]), discarded=[("ts-bool-env", 0)])
    result = analyze(run, require_full_roster=False)
    assert result["admitted_cells"] == 1
    assert result["contrasts"]["c9_norm_minus_code4_replay"]["all"]["difference"] == 0.0


def test_an_incomplete_cell_stops_the_analysis(tmp_path: Path) -> None:
    outcomes = _grid([True, False])
    del outcomes[("ts-bool-env", 1, "c9_raw")]
    with pytest.raises(Exception) as refused:  # noqa: B017, PT011: any failure, then its message
        analyze(_write_run(tmp_path, outcomes), require_full_roster=False)
    assert "not complete" in str(refused.value)


def test_evidence_changing_across_seeds_stops_it(tmp_path: Path) -> None:
    run = _write_run(tmp_path, _grid([True, False]))
    rows = [json.loads(line) for line in (run / "records.final.jsonl").read_text().split("\n") if line]
    rows[-1]["metadata"]["memory_diagnostic"]["injected_text_sha256"] = "0" * 64
    (run / "records.final.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="changed across seeds"):
        analyze(run, require_full_roster=False)


def test_a_record_naming_another_artifact_stops_it(tmp_path: Path) -> None:
    run = _write_run(tmp_path, _grid([True]))
    rows = [json.loads(line) for line in (run / "records.final.jsonl").read_text().split("\n") if line]
    rows[1]["metadata"]["memory_diagnostic"]["artifact_sha256"] = CODE4
    (run / "records.final.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact_sha256 mismatch"):
        analyze(run, require_full_roster=False)
