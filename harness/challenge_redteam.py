"""Static red team checks for AMB challenge plans and Docker commands."""

from __future__ import annotations

from collections.abc import Sequence

from .challenge_pack import ChallengeExecutionPlan


class ChallengeRedTeamError(ValueError):
    """A challenge command violates the minimum isolation policy."""


FORBIDDEN_TOKENS = (
    "--privileged",
    "--cap-add",
    "--network=host",
    "--pid=host",
    "--ipc=host",
    "--uts=host",
    "/var/run/docker.sock",
)
REQUIRED_TOKENS = (
    "--pull=never",
    "--read-only",
    "--cap-drop=ALL",
    "--network=none",
    "no-new-privileges:true",
)


def audit_plan(plan: ChallengeExecutionPlan) -> None:
    """Reject private, cross task or result mounts before Docker is invoked."""

    names = {mount.get("name") for mount in plan.mounts}
    expected = {"fixture", "prompt", "corpus", "output"}
    if names != expected:
        raise ChallengeRedTeamError(f"unexpected challenge mount set: {sorted(names)!r}")
    for mount in plan.mounts:
        name = mount.get("name")
        if name in {"checker", "oracle", "reference", "private", "evaluator"}:
            raise ChallengeRedTeamError(f"private mount is present: {name!r}")


def audit_docker_argv(argv: Sequence[str], *, sidecar: bool = False) -> None:
    """Check the rendered Docker argv for forbidden privileges and mounts."""

    command = " ".join(argv)
    for token in FORBIDDEN_TOKENS:
        if token in command:
            raise ChallengeRedTeamError(f"forbidden Docker token present: {token}")
    for token in REQUIRED_TOKENS:
        if token not in command:
            raise ChallengeRedTeamError(f"required Docker token missing: {token}")
    if sidecar:
        for private_target in ("/challenge/task", "/challenge/prompt.txt", "/challenge/output"):
            if private_target in command:
                raise ChallengeRedTeamError(f"sidecar exposes forbidden target: {private_target}")
