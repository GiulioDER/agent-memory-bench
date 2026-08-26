"""The leaderboard page promises no number is typed in by hand. This is the enforcement."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_leaderboard.py"

ARMS = ["recall", "mem0", "supermemory", "zep", "cognee", "fs_grep", "claude_md", "bare"]


def _run(*args, root=None):
    cmd = [sys.executable, str(SCRIPT), *args]
    if root is not None:
        cmd += ["--root", str(root)]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _summary():
    arm = {
        "success": 0.5,
        "delta": 0.1,
        "ci": [0.0, 0.2],
        "discarded": 1,
        "tokensPerTask": 200,
        "costPerTask": 1.25,
    }
    arms = {name: dict(arm) for name in ARMS}
    arms["claude_md"]["delta"] = 0
    return {
        "run": {
            "id": "run-x",
            "date": "2026-09-01",
            "cli": "2.1.230",
            "model": "test-model",
            "tasks": 24,
            "sessionsPerCell": 3,
            "prereg": "preregistration/005-run-x.md",
        },
        "arms": arms,
        "reference": {
            "oracle_memory": {"success": 0.8, "delta": 0.4},
            "recall_prefetch": {"success": 0.6, "delta": 0.2},
        },
    }


def _scaffold(tmp_path, summary=None, official_run=None):
    data = tmp_path / "site" / "data"
    data.mkdir(parents=True)
    (data / "leaderboard.config.json").write_text(
        json.dumps({"official_run": official_run, "updated": "2026-08-26"}),
        encoding="utf-8",
    )
    if summary is not None:
        run_dir = tmp_path / "results" / official_run
        run_dir.mkdir(parents=True)
        (run_dir / "leaderboard_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
    return tmp_path


def _payload(root):
    text = (root / "site" / "data" / "leaderboard.js").read_text(encoding="utf-8")
    return json.loads(text.split("window.AMB_LEADERBOARD = ", 1)[1].rstrip().rstrip(";"))


def test_committed_leaderboard_matches_its_regeneration():
    result = _run("--check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_hand_edited_number_fails_the_check(tmp_path):
    root = _scaffold(tmp_path)
    assert _run(root=root).returncode == 0
    out = root / "site" / "data" / "leaderboard.js"
    out.write_text(
        out.read_text(encoding="utf-8").replace('"success": null', '"success": 0.99', 1),
        encoding="utf-8",
    )
    result = _run("--check", root=root)
    assert result.returncode == 1
    assert "Never edit it by hand" in result.stdout


def test_phase0_emits_null_run_and_pending_numbers(tmp_path):
    root = _scaffold(tmp_path)
    assert _run(root=root).returncode == 0
    data = _payload(root)
    assert data["run"] is None
    assert [a["name"] for a in data["arms"]] == ARMS
    baseline = next(a for a in data["arms"] if a["name"] == "claude_md")
    assert baseline["delta"] == 0 and baseline["success"] is None


def test_official_summary_fills_the_page(tmp_path):
    root = _scaffold(tmp_path, summary=_summary(), official_run="run-x")
    result = _run(root=root)
    assert result.returncode == 0, result.stdout + result.stderr
    data = _payload(root)
    assert data["run"]["id"] == "run-x"
    recall = next(a for a in data["arms"] if a["name"] == "recall")
    assert recall["success"] == 0.5 and recall["costPerTask"] == 1.25


def test_a_summary_missing_an_arm_is_refused(tmp_path):
    summary = _summary()
    del summary["arms"]["bare"]
    root = _scaffold(tmp_path, summary=summary, official_run="run-x")
    result = _run(root=root)
    assert result.returncode != 0
    assert "bare" in result.stderr


def test_a_moved_baseline_is_refused(tmp_path):
    summary = _summary()
    summary["arms"]["claude_md"]["delta"] = 0.01
    root = _scaffold(tmp_path, summary=summary, official_run="run-x")
    result = _run(root=root)
    assert result.returncode != 0
    assert "baseline" in result.stderr
