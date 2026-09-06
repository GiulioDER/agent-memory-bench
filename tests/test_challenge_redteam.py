"""Tests for static challenge red team checks."""

from __future__ import annotations

import json

import pytest

from scripts.run_challenge_red_team import _image_digest
from harness.challenge_redteam import (
    ChallengeRedTeamError,
    audit_docker_argv,
    validate_red_team_report,
    write_red_team_report,
)
from harness.challenge_runner import ChallengeRunnerError


def test_red_team_requires_isolation_tokens():
    audit_docker_argv(
        [
            "docker",
            "run",
            "--pull=never",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--network=none",
        ]
    )


@pytest.mark.parametrize("token", ["--privileged", "--network=host", "--pid=host", "--cap-add"])
def test_red_team_rejects_forbidden_tokens(token: str):
    with pytest.raises(ChallengeRedTeamError, match="forbidden"):
        audit_docker_argv(
            [
                "docker",
                "run",
                "--pull=never",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--network=none",
                token,
            ]
        )


def test_red_team_rejects_private_sidecar_targets():
    with pytest.raises(ChallengeRedTeamError, match="forbidden target"):
        audit_docker_argv(
            [
                "docker",
                "run",
                "--pull=never",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--network=none",
                "--mount",
                "/challenge/output",
            ],
            sidecar=True,
        )


def test_red_team_report_is_immutable_and_requires_an_image_digest(tmp_path):
    image = "registry.example/probe@sha256:" + "a" * 64
    report_path = tmp_path / "red-team.json"
    write_red_team_report(report_path, image)
    assert validate_red_team_report(json.loads(report_path.read_text())) == image
    write_red_team_report(report_path, image)
    with pytest.raises(ChallengeRedTeamError, match="immutable digest"):
        validate_red_team_report(
            {"schema": 1, "kind": "amb-challenge-red-team-report", "status": "pass", "image": "ubuntu:24.04"}
        )


def test_red_team_rejects_malformed_pinned_image_before_docker():
    with pytest.raises(ChallengeRunnerError, match="valid immutable digest"):
        _image_digest("ubuntu@sha256:too-short", "docker")
