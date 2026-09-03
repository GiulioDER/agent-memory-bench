from __future__ import annotations

import json

from scripts.abstention_trace import _condition_dirs


def test_condition_discovery_accepts_a_direct_pilot_run(tmp_path) -> None:
    run_id = "direct-smoke"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    (run_dir / "records.final.jsonl").write_text(
        json.dumps({"metadata": {"condition": "superseded"}}) + "\n",
        encoding="utf-8",
    )

    assert _condition_dirs(tmp_path, run_id) == [("superseded", run_dir)]


def test_condition_discovery_prefers_wrapper_directories(tmp_path) -> None:
    run_id = "wrapped-smoke"
    wrapped = tmp_path / f"{run_id}-superseded"
    wrapped.mkdir()

    assert _condition_dirs(tmp_path, run_id) == [("superseded", wrapped)]
