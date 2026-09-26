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
    # The PUBLIC name since 2026-09-26; the report behind it still says `recall`, the internal id.
    assert data["analysis"]["best_visible_memory"]["arm"] == "RE-call"
    assert data["analysis"]["arms"]["mempalace"]["status"] == "published"


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


def test_additive_vendor_submission_is_projected_into_analysis(tmp_path):
    analyzer = _module(SCRIPT, "analyze_official_additive_test")
    builder = _module(LEADERBOARD_SCRIPT, "build_leaderboard_additive_test")
    results = tmp_path / "results"
    base_dir = results / "run-x"
    vendor_dir = results / "cognee-x"
    base_dir.mkdir(parents=True)
    vendor_dir.mkdir()
    base_arms = {
        name: {
            "success": 0.5,
            "delta": 0.0,
            "ci": [0.0, 0.0],
            "discarded": 0,
            "tokensPerTask": 1,
            "costPerTask": 1.0,
            "totalTokens": 1,
        }
        for name, *_ in builder.PRODUCT_ARMS
    }
    summary = {
        "run": {
            "id": "run-x",
            "date": "2026-09-04",
            "cli": "claude-code",
            "model": "model-x",
            "tasks": 1,
            "sessionsPerCell": 1,
            "prereg": "preregistration/x.md",
        },
        "arms": base_arms,
        "reference": {name: {"success": 0.5, "delta": 0.0} for name, _ in builder.REFERENCE_TRACKS},
    }
    (base_dir / "leaderboard_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    submission = {
        "schema": 1,
        "generated_by": "scripts/build_arm_submission.py",
        "run": {**summary["run"], "id": "cognee-x", "date": "2026-09-04"},
        "arm": "cognee",
        "base_run": "run-x",
        "result": {
            "success": 0.75,
            "delta": 0.25,
            "ci": [0.1, 0.4],
            "discarded": 0,
            "totalTokens": 800,
            "tokensPerTask": 100,
            "costPerTask": 0.5,
            "byCondition": {condition: {"solved": 1, "cells": 1} for condition in analyzer.CONDITIONS},
        },
        "join": {"baseRun": "run-x", "baseAdmittedCells": 5, "joinedCells": 5, "baseCellsLostToJoin": 0, "conditions": list(analyzer.CONDITIONS)},
    }
    (vendor_dir / "arm_summary.json").write_text(json.dumps(submission), encoding="utf-8")
    site_data = tmp_path / "site" / "data"
    site_data.mkdir(parents=True)
    (site_data / "leaderboard.config.json").write_text(json.dumps({"official_run": "run-x", "arm_runs": {"cognee": "cognee-x"}}), encoding="utf-8")

    projected = analyzer._additive_arm_analysis(
        tmp_path,
        "run-x",
        summary,
        {"by_condition": {condition: {"success": 0.5} for condition in analyzer.CONDITIONS}},
    )["cognee"]
    assert projected["comparison"] == "joined to run-x"
    assert projected["cost"]["reported_usd_per_task"] == 0.5
    assert projected["condition_delta_vs_baseline"]["present"] == 0.5


@pytest.mark.parametrize(
    ("delta", "ci95", "expected"),
    [
        pytest.param(
            -0.3285,
            [-0.3904, -0.1101],
            "product_x is below the claude_md baseline at -32.9%, and its published 95% interval [-39.0%, -11.0%] excludes zero.",
            id="negative-excludes-zero",
        ),
        pytest.param(
            0.2,
            [0.05, 0.3],
            "product_x is above the claude_md baseline at +20.0%, and its published 95% interval [+5.0%, +30.0%] excludes zero.",
            id="positive-excludes-zero",
        ),
        pytest.param(
            -0.05,
            [-0.1, 0.02],
            "product_x shows a negative point estimate, but its published 95% interval crosses zero.",
            id="negative-crosses-zero",
        ),
        pytest.param(
            0.082,
            [-0.01, 0.17],
            "product_x shows a positive point estimate, but its published 95% interval crosses zero.",
            id="positive-crosses-zero",
        ),
    ],
)
def test_insights_state_the_direction_and_whether_the_interval_excludes_zero(delta, ci95, expected):
    """Every visible product with a nonzero delta gets exactly one sign line, whichever its sign.

    Invariant: the published insights name the direction of each product's point estimate against
    the claude_md baseline, and say "excludes zero" rather than "crosses zero" when the 95%
    interval lies wholly on one side. Failure mode: before this test, `_insights` only spoke about
    a positive estimate whose interval crossed zero, so supermemory in official-003 (delta
    -0.3285, ci95 [-0.3904, -0.1101], the only arm whose interval excludes zero) got no line at all.

    Red proof, recorded 2026-09-26, node
    `tests/test_official_analysis.py::test_insights_state_the_direction_and_whether_the_interval_excludes_zero[<id>]`:
    * Baseline: `scripts/analyze_official.py` at abd4e6bc (pre-fix `_insights`). The three new
      cases `negative-excludes-zero`, `positive-excludes-zero` and `negative-crosses-zero` failed
      in the `assert lines == [expected]` assertion with `lines == []`.
    * `positive-crosses-zero` passes at abd4e6bc by design: it guards the wording that already
      shipped. Its red proof is a mutation of the fixed `_insights`, swapping the "positive" and
      "negative" direction words, which failed it in the same assertion.
    Green after restoring the fixed implementation.
    """
    analyzer = _module(SCRIPT, "analyze_official_insight_sign_test")
    arms = {
        "claude_md": {"success": 0.5773, "delta_vs_baseline": 0.0, "ci95": None},
        "product_x": {"success": 0.5773 + delta, "delta_vs_baseline": delta, "ci95": ci95, "cost": {}},
    }
    insights = analyzer._insights(arms, {}, {}, ("product_x",))
    lines = [line for line in insights if line.startswith("product_x ") and "interval" in line]
    assert lines == [expected]
