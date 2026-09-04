"""Guards for the generated official run analysis and its leaderboard binding."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "analyze_official.py"
LEADERBOARD_SCRIPT = REPO_ROOT / "scripts" / "build_leaderboard.py"


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_committed_official_analysis_reproduces_from_evidence():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--run-id", "official-003", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_leaderboard_committed_data_includes_the_analysis_layer():
    payload = (REPO_ROOT / "site" / "data" / "leaderboard.js").read_text(encoding="utf-8")
    data = json.loads(payload.split("window.AMB_LEADERBOARD = ", 1)[1].rstrip().rstrip(";"))
    assert data["analysis"]["headline"] == "No clear memory winner"
    assert data["analysis"]["best_visible_memory"]["arm"] == "recall"
    assert data["analysis"]["arms"]["mempalace"]["status"] == "held"


def test_analysis_binding_rejects_a_stale_summary(tmp_path):
    generator = _module(LEADERBOARD_SCRIPT, "build_leaderboard_for_analysis_test")
    run_dir = tmp_path / "results" / "run-x"
    run_dir.mkdir(parents=True)
    summary_path = run_dir / "leaderboard_summary.json"
    summary_path.write_text('{"run": {"id": "run-x"}}', encoding="utf-8")
    report_path = tmp_path / "reports" / "run-x-analysis.json"
    report_path.parent.mkdir()
    report_path.write_text(
        json.dumps(
            {
                "generated_by": "scripts/analyze_official.py",
                "run": {"id": "run-x"},
                "sources": {"summary_sha256": "stale"},
                "leaderboard": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(generator.SummaryInvalid, match="stale"):
        generator._load_analysis(tmp_path, "run-x", "reports/run-x-analysis.json")
