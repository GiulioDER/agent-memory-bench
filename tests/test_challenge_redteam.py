"""Tests for static challenge red team checks."""

from __future__ import annotations

import pytest

from harness.challenge_redteam import ChallengeRedTeamError, audit_docker_argv


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
