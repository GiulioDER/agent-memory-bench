"""Tests for the aggregate challenge readiness report."""

from __future__ import annotations

import json
from pathlib import Path

from harness.challenge_pack import load_private_pack
from harness.challenge_policy import load_policy
from harness.challenge_readiness import evaluate_readiness, readiness_result
from harness.challenge_release import (
    build_release_manifest,
    hash_private_pack,
    write_release_manifest,
)
from harness.challenge_rules import rules_digest


def _private_pack(root: Path):
    files = {
        "corpus/session.txt": "memory only",
        "fixtures/task-a/input.txt": "fixture",
        "prompts/task-a.txt": "prompt",
        "checkers/task-a/checker.py": "checker",
        "oracles/task-a/value.txt": "secret oracle",
        "references/task-a/answer.txt": "reference",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (root / "pack.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "amb-private-evaluation-pack",
                "visibility": "private",
                "pack_id": "pack-readiness",
                "source_public_commit": "commit-readiness",
                "scoring_version": "score-readiness",
                "prepared_by": "pack-author",
                "corpus": "corpus",
                "tasks": [
                    {
                        "task_id": "task-a",
                        "fixture": "fixtures/task-a",
                        "prompt": "prompts/task-a.txt",
                        "checker": "checkers/task-a/checker.py",
                        "oracle": "oracles/task-a",
                        "reference": "references/task-a",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return load_private_pack(root)


def test_readiness_reports_missing_external_gates(tmp_path: Path):
    result = readiness_result(
        evaluate_readiness(
            tmp_path / "missing-pack",
            tmp_path / "missing-policy",
            tmp_path / "missing-rules",
        )
    )
    assert result["status"] == "blocked"
    assert {gate["name"] for gate in result["gates"]} == {
        "private_pack",
        "public_smoke",
        "corpus_leakage",
        "container_isolation",
        "task_roster_review",
        "evaluation_policy",
        "final_rules",
        "release_record",
        "baseline_ordering",
    }


def test_readiness_requires_both_baseline_manifests(tmp_path: Path):
    for name, score in (("baseline.json", 0.8), ("bad.json", 0.1)):
        (tmp_path / name).write_text(json.dumps({"score": score}), encoding="utf-8")
    result = evaluate_readiness(
        tmp_path / "missing-pack",
        tmp_path / "missing-policy",
        tmp_path / "missing-rules",
        baseline_path=tmp_path / "baseline.json",
    )
    gate = next(gate for gate in result if gate.name == "baseline_ordering")
    assert gate.passed is False


def test_readiness_passes_with_valid_private_release_inputs(tmp_path: Path):
    pack = _private_pack(tmp_path / "pack")
    policy_path = tmp_path / "policy.json"
    policy = {
        "schema": 1,
        "kind": "amb-challenge-evaluation-policy",
        "policy_id": "policy-readiness",
        "agent_command_sha256": "a" * 64,
        "agent_timeout_seconds": 10,
        "checker_timeout_seconds": 10,
        "adapter_call_budget": 8,
        "model_id": "model-readiness",
        "provider_id": "provider-readiness",
        "temperature": 0,
        "context_limit_tokens": 1024,
        "infrastructure_retries": 0,
    }
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "amb-challenge-rules",
                "rules_id": "rules-readiness",
                "status": "final",
                "prize_total_usd": 200,
                "winner_count": 1,
                "appeal_window_days": 7,
                "entry_deadline_utc": "2026-10-01T23:59:59Z",
                "tie_breaker_task_ids": ["task-a"],
                "excluded_submission_ids": ["sponsor-reference"],
                "independent_reviewer_count": 1,
                "sponsor_entry_eligible": False,
                "infrastructure_retry_count": 0,
                "baseline_minimum_margin": 0.1,
                "appeal_scope": "evaluator defect",
                "publication": {
                    "publish_failed_entries": True,
                    "publish_score_manifest": True,
                    "publish_submission_image_digest": True,
                },
            }
        ),
        encoding="utf-8",
    )
    loaded_policy = load_policy(policy_path)
    release_path = tmp_path / "release.json"
    write_release_manifest(
        release_path,
        build_release_manifest(
            pack,
            loaded_policy,
            json.loads(rules_path.read_text()),
            evaluator_revision="a" * 40,
        ),
    )
    baseline_path = tmp_path / "baseline.json"
    bad_path = tmp_path / "bad.json"
    pack_digest = hash_private_pack(pack)
    frozen_rules_digest = rules_digest(json.loads(rules_path.read_text()))
    def manifest(score: float, passed_count: int, submission_id: str) -> dict:
        return {
            "schema": 1,
            "kind": "amb-challenge-score-manifest",
            "pack_id": "pack-readiness",
            "scoring_version": "score-readiness",
            "pack_digest": pack_digest,
            "rules_digest": frozen_rules_digest,
            "evaluator_revision": "a" * 40,
                "policy_digest": loaded_policy.digest(),
                "config_sha256": "d" * 64,
            "submission_id": submission_id,
            "image": "registry.example/entry@sha256:" + "a" * 64,
            "task_count": 1,
            "passed_count": passed_count,
            "score": score,
            "tasks": [
                {
                    "task_id": "task-a",
                    "passed": bool(passed_count),
                    "checker_returncode": 0,
                    "checker_timed_out": False,
                }
            ],
            "private_details_included": False,
        }

    baseline_path.write_text(json.dumps(manifest(1.0, 1, "baseline")), encoding="utf-8")
    bad_path.write_text(json.dumps(manifest(0.0, 0, "bad")), encoding="utf-8")
    red_team_path = tmp_path / "red-team.json"
    red_team_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "amb-challenge-red-team-report",
                "status": "pass",
                "image": "registry.example/probe@sha256:" + "a" * 64,
            }
        ),
        encoding="utf-8",
    )
    roster_review_path = tmp_path / "roster-review.json"
    roster_review_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "amb-challenge-roster-review",
                "status": "pass",
                "pack_digest": pack_digest,
                "task_count": 1,
                "task_ids": ["task-a"],
                "reviewer_id": "independent-reviewer",
                "pack_preparer_id": "pack-author",
                "independent_review": True,
                "reviewed_at_utc": "2026-09-06T12:00:00Z",
                "checks": {
                    name: {"status": "pass", "evidence": f"{name} reviewed"}
                    for name in ("capacity", "leakage", "overlap", "findability")
                },
            }
        ),
        encoding="utf-8",
    )
    smoke_path = tmp_path / "public-smoke.json"
    smoke_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "amb-challenge-public-smoke-report",
                "status": "pass",
                "repository_revision": "a" * 40,
                "python_version": "3.12.11",
                "credentials_required": False,
                "database_required": False,
                "commands": [
                    {"name": name, "status": "pass"}
                    for name in (
                        "ruff",
                        "pytest",
                        "audit_corpus",
                        "audit_plants",
                        "diagnostic_dry_run",
                        "pilot_dry_run",
                    )
                ],
                "tests_passed": 1120,
                "tests_skipped": 17,
            }
        ),
        encoding="utf-8",
    )

    result = readiness_result(
        evaluate_readiness(
            pack.root,
            policy_path,
            rules_path,
            release_path=release_path,
            baseline_path=baseline_path,
            deliberately_bad_path=bad_path,
            red_team_report_path=red_team_path,
            roster_review_path=roster_review_path,
            public_smoke_report_path=smoke_path,
            evaluator_revision="a" * 40,
        )
    )
    assert result["status"] == "pass"

    invalid_revision = readiness_result(
        evaluate_readiness(
            pack.root,
            policy_path,
            rules_path,
            release_path=release_path,
            baseline_path=baseline_path,
            deliberately_bad_path=bad_path,
            red_team_report_path=red_team_path,
            roster_review_path=roster_review_path,
            public_smoke_report_path=smoke_path,
            evaluator_revision="dirty",
        )
    )
    release_gate = next(gate for gate in invalid_revision["gates"] if gate["name"] == "release_record")
    assert release_gate["passed"] is False

    invalid_release = json.loads(release_path.read_text(encoding="utf-8"))
    invalid_release["schema"] = 99
    release_path.write_text(json.dumps(invalid_release), encoding="utf-8")
    invalid_schema = readiness_result(
        evaluate_readiness(
            pack.root,
            policy_path,
            rules_path,
            release_path=release_path,
            baseline_path=baseline_path,
            deliberately_bad_path=bad_path,
            red_team_report_path=red_team_path,
            roster_review_path=roster_review_path,
            public_smoke_report_path=smoke_path,
            evaluator_revision="a" * 40,
        )
    )
    release_gate = next(gate for gate in invalid_schema["gates"] if gate["name"] == "release_record")
    assert release_gate["passed"] is False
