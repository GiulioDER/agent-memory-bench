"""Static red team checks for AMB challenge plans and Docker commands."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .challenge_pack import IMAGE_DIGEST, ChallengeExecutionPlan


class ChallengeRedTeamError(ValueError):
    """A challenge command violates the minimum isolation policy."""


def validate_red_team_report(data: Any) -> str:
    """Validate a successful dynamic red team report and return its image digest."""

    if not isinstance(data, dict):
        raise ChallengeRedTeamError("red team report must contain an object")
    if (
        type(data.get("schema")) is not int
        or data["schema"] != 1
        or data.get("kind") != "amb-challenge-red-team-report"
    ):
        raise ChallengeRedTeamError("unsupported red team report")
    if data.get("status") != "pass":
        raise ChallengeRedTeamError("red team report does not record a pass")
    image = data.get("image")
    if not isinstance(image, str) or not IMAGE_DIGEST.fullmatch(image):
        raise ChallengeRedTeamError("red team report image must use an immutable digest")
    return image


def write_red_team_report(path: str | Path, image: str) -> None:
    """Write one immutable successful red team report."""

    validate_red_team_report(
        {"schema": 1, "kind": "amb-challenge-red-team-report", "status": "pass", "image": image}
    )
    target = Path(path).expanduser()
    if target.exists() and target.is_symlink():
        raise ChallengeRedTeamError(f"red team report target must not be a symlink: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(
        {"schema": 1, "kind": "amb-challenge-red-team-report", "status": "pass", "image": image},
        indent=2,
        sort_keys=True,
    ) + "\n"
    if target.exists():
        if not target.is_file() or target.read_text(encoding="utf-8") != content:
            raise ChallengeRedTeamError(f"red team report target already contains different data: {target}")
        return
    try:
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as error:
        raise ChallengeRedTeamError(f"red team report target already exists: {target}") from error


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

    values = list(argv)
    try:
        image_end = values.index("--entrypoint") + 2
    except ValueError:
        image_end = len(values)
    command = " ".join(values[:image_end])
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
