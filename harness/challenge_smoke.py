"""Validate the fresh-machine public smoke evidence required before a prize run."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .challenge_release import validate_evaluator_revision

SMOKE_SCHEMA = 1
SMOKE_KIND = "amb-challenge-public-smoke-report"
REQUIRED_COMMANDS = (
    "ruff",
    "pytest",
    "audit_corpus",
    "audit_plants",
    "diagnostic_dry_run",
    "pilot_dry_run",
)


class ChallengeSmokeError(ValueError):
    """The public fresh-machine smoke evidence is missing or invalid."""


def validate_public_smoke_report(
    data: Any,
    *,
    expected_repository_revision: str | None = None,
) -> dict[str, Any]:
    """Validate one successful smoke report without trusting its command output."""

    if not isinstance(data, dict):
        raise ChallengeSmokeError("public smoke report must contain an object")
    if data.get("schema") != SMOKE_SCHEMA or data.get("kind") != SMOKE_KIND:
        raise ChallengeSmokeError("unsupported public smoke report")
    if data.get("status") != "pass":
        raise ChallengeSmokeError("public smoke report does not record a pass")
    try:
        repository_revision = validate_evaluator_revision(
            data.get("repository_revision")
        )
        if expected_repository_revision is not None:
            expected_repository_revision = validate_evaluator_revision(
                expected_repository_revision
            )
    except ValueError as error:
        raise ChallengeSmokeError(str(error)) from error
    if (
        expected_repository_revision is not None
        and repository_revision != expected_repository_revision
    ):
        raise ChallengeSmokeError("public smoke report does not match the evaluator revision")
    if not isinstance(data.get("python_version"), str) or not data["python_version"].strip():
        raise ChallengeSmokeError("public smoke report needs python_version")
    if data.get("credentials_required") is not False:
        raise ChallengeSmokeError("public smoke must declare credentials_required=false")
    if data.get("database_required") is not False:
        raise ChallengeSmokeError("public smoke must declare database_required=false")
    commands = data.get("commands")
    if not isinstance(commands, list):
        raise ChallengeSmokeError("public smoke report needs a commands list")
    names: list[str] = []
    for command in commands:
        if not isinstance(command, dict):
            raise ChallengeSmokeError("public smoke commands must be objects")
        name = command.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ChallengeSmokeError("public smoke commands must have unique names")
        if command.get("status") != "pass":
            raise ChallengeSmokeError(f"public smoke command {name!r} did not pass")
        names.append(name)
    if tuple(names) != REQUIRED_COMMANDS:
        raise ChallengeSmokeError(
            "public smoke commands must cover " + ", ".join(REQUIRED_COMMANDS)
        )
    for field in ("tests_passed", "tests_skipped"):
        value = data.get(field)
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or (value < 0 if field == "tests_skipped" else value <= 0)
        ):
            raise ChallengeSmokeError(f"public smoke report has invalid {field}")
    return data


def command_names(commands: Iterable[str]) -> tuple[str, ...]:
    """Return the canonical command sequence for report producers."""

    return tuple(commands)
