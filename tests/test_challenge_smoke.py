from __future__ import annotations

import pytest

from harness.challenge_smoke import ChallengeSmokeError, validate_public_smoke_report
from scripts.run_challenge_public_smoke import (
    PublicSmokeError,
    _clean_environment,
    _pytest_counts,
    _write_immutable,
)


def _report() -> dict:
    return {
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


def test_public_smoke_report_accepts_complete_fresh_machine_evidence():
    report = validate_public_smoke_report(_report(), expected_repository_revision="a" * 40)
    assert report["tests_passed"] == 1120


def test_public_smoke_requires_python_312():
    report = _report()
    report["python_version"] = "3.11.9"
    with pytest.raises(ChallengeSmokeError, match="Python 3.12"):
        validate_public_smoke_report(report)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda report: report.update({"credentials_required": True}),
        lambda report: report["commands"].pop(),
        lambda report: report.update({"repository_revision": "b" * 40}),
    ),
)
def test_public_smoke_report_rejects_incomplete_or_unbound_evidence(mutation):
    report = _report()
    mutation(report)
    with pytest.raises(ChallengeSmokeError):
        validate_public_smoke_report(report, expected_repository_revision="a" * 40)


def test_smoke_producer_parses_final_pytest_counts():
    assert _pytest_counts("================ 1132 passed, 17 skipped in 12s ================") == (1132, 17)


def test_smoke_producer_does_not_overwrite_different_evidence(tmp_path):
    target = tmp_path / "smoke.json"
    _write_immutable(target, {"status": "pass"})
    with pytest.raises(PublicSmokeError, match="already contains different data"):
        _write_immutable(target, {"status": "different"})


def test_smoke_producer_uses_an_environment_allowlist(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://secret")
    assert "OPENAI_API_KEY" not in _clean_environment()
    assert "DATABASE_URL" not in _clean_environment()
