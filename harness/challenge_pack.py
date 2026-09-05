"""Validate the private evaluation pack used by the AMB prize challenge.

The public repository is deliberately not a valid challenge pack. It contains the development
oracles and reference implementations needed to audit the benchmark, so a prize evaluator must
receive a separate pack whose paths are validated before any submission is executed.

This module validates pack structure and path containment only. It does not claim to sandbox an
untrusted adapter or agent. That remains the responsibility of the evaluator process.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

PUBLIC_REPO_ROOT = Path(__file__).resolve().parent.parent.resolve()
PACK_SCHEMA = 1
PACK_KIND = "amb-private-evaluation-pack"
TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IMAGE_DIGEST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9./:_-]*@sha256:[0-9a-f]{64}$")
TASK_PATHS = ("fixture", "prompt", "checker", "oracle", "reference")
SUBMISSION_API = "amb-challenge-adapter-v1"


class ChallengePackError(ValueError):
    """The supplied private evaluation pack cannot be trusted structurally."""


@dataclass(frozen=True)
class ChallengeTask:
    task_id: str
    fixture: Path
    prompt: Path
    checker: Path
    oracle: Path
    reference: Path


@dataclass(frozen=True)
class ChallengePack:
    root: Path
    manifest: dict[str, Any]
    corpus: Path
    tasks: tuple[ChallengeTask, ...]


@dataclass(frozen=True)
class ChallengeSubmission:
    submission_id: str
    image: str
    source_revision: str
    adapter_api: str
    config_sha256: str
    network: str
    entrypoint: tuple[str, ...]


@dataclass(frozen=True)
class ChallengeExecutionPlan:
    """The only mounts one isolated challenge task may receive.

    This is an abstract plan, not a Docker invocation. The evaluator still has to turn it into a
    container command and enforce the listed properties on the host that performs the run.
    """

    submission_id: str
    image: str
    network: str
    task_id: str
    mounts: tuple[dict[str, Any], ...]
    security: dict[str, Any]
    entrypoint: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "image": self.image,
            "network": self.network,
            "task_id": self.task_id,
            "mounts": [dict(mount) for mount in self.mounts],
            "security": dict(self.security),
            "entrypoint": list(self.entrypoint),
        }


def _reject_public_overlap(root: Path) -> None:
    for candidate, label in (
        (root, "private pack"),
        (PUBLIC_REPO_ROOT, "public repository"),
    ):
        try:
            candidate.relative_to(root if label == "public repository" else PUBLIC_REPO_ROOT)
        except ValueError:
            continue
        if label == "private pack":
            raise ChallengePackError(
                f"{label} is inside the public repository: {root}; use a separate private location"
            )
        raise ChallengePackError(
            f"private pack contains the public repository: {root}; keep evaluator files separate"
        )


def _safe_relative_path(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChallengePackError(f"task {field!r} must be a non empty relative path")
    if (
        PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).is_absolute()
        or PureWindowsPath(value).drive
        or "\\" in value
    ):
        raise ChallengePackError(f"task {field!r} is not a portable relative path: {value!r}")
    path = PurePosixPath(value)
    if any(part in ("", ".", "..") for part in path.parts):
        raise ChallengePackError(f"task {field!r} contains an unsafe path: {value!r}")
    return value


def _resolve_pack_path(root: Path, value: Any, field: str, *, directory: bool) -> Path:
    relative = _safe_relative_path(value, field)
    candidate = (root / Path(*PurePosixPath(relative).parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ChallengePackError(f"task {field!r} escapes the private pack") from error

    current = candidate
    while True:
        if current.is_symlink():
            raise ChallengePackError(f"task {field!r} uses a symlink: {relative!r}")
        if current == root:
            break
        current = current.parent

    if not candidate.exists():
        raise ChallengePackError(f"task {field!r} does not exist: {relative!r}")
    if candidate.is_dir() != directory:
        expected = "directory" if directory else "file"
        raise ChallengePackError(f"task {field!r} is not a {expected}: {relative!r}")
    return candidate


def _validate_manifest(root: Path, data: Any) -> ChallengePack:
    if not isinstance(data, dict):
        raise ChallengePackError("pack.json must contain an object")
    if data.get("schema") != PACK_SCHEMA:
        raise ChallengePackError(f"unsupported pack schema: {data.get('schema')!r}")
    if data.get("kind") != PACK_KIND:
        raise ChallengePackError(f"pack.json kind must be {PACK_KIND!r}")
    if data.get("visibility") != "private":
        raise ChallengePackError("pack.json must declare visibility='private'")
    for field in ("pack_id", "source_public_commit", "scoring_version"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ChallengePackError(f"pack.json field {field!r} must be a non empty string")
    corpus = _resolve_pack_path(root, data.get("corpus"), "corpus", directory=True)

    raw_tasks = data.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ChallengePackError("pack.json tasks must be a non empty list")

    tasks: list[ChallengeTask] = []
    seen: set[str] = set()
    for raw in raw_tasks:
        if not isinstance(raw, dict):
            raise ChallengePackError("each challenge task must be an object")
        task_id = raw.get("task_id")
        if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
            raise ChallengePackError(f"invalid challenge task id: {task_id!r}")
        if task_id in seen:
            raise ChallengePackError(f"duplicate challenge task id: {task_id!r}")
        seen.add(task_id)
        paths = {
            field: _resolve_pack_path(
                root,
                raw.get(field),
                field,
                directory=field in ("fixture", "oracle", "reference"),
            )
            for field in TASK_PATHS
        }
        tasks.append(ChallengeTask(task_id=task_id, **paths))
    return ChallengePack(root=root, manifest=data, corpus=corpus, tasks=tuple(tasks))


def load_private_pack(path: str | Path) -> ChallengePack:
    """Load and structurally validate one private challenge pack."""

    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ChallengePackError(f"private pack directory does not exist: {root}")
    _reject_public_overlap(root)
    manifest_path = root / "pack.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ChallengePackError(f"private pack has no regular pack.json: {manifest_path}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ChallengePackError(f"cannot read private pack manifest: {manifest_path}") from error

    for entry in root.rglob("*"):
        if entry.is_symlink():
            raise ChallengePackError(
                f"private pack contains a symlink: {entry.relative_to(root)}"
            )
    return _validate_manifest(root, data)


def _required_string(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ChallengePackError(f"submission field {field!r} must be a non empty string")
    return value


def load_submission(path: str | Path) -> ChallengeSubmission:
    """Load a submission descriptor without executing or importing entrant code."""

    descriptor = Path(path).expanduser().resolve()
    if descriptor.is_symlink() or not descriptor.is_file():
        raise ChallengePackError(f"submission descriptor is not a regular file: {descriptor}")
    try:
        data = json.loads(descriptor.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ChallengePackError(f"cannot read submission descriptor: {descriptor}") from error
    if not isinstance(data, dict):
        raise ChallengePackError("submission descriptor must contain an object")
    if data.get("schema") != PACK_SCHEMA:
        raise ChallengePackError(f"unsupported submission schema: {data.get('schema')!r}")
    if data.get("kind") != "amb-challenge-submission":
        raise ChallengePackError("submission kind must be 'amb-challenge-submission'")

    submission_id = _required_string(data, "submission_id")
    if not TASK_ID.fullmatch(submission_id):
        raise ChallengePackError(f"invalid submission id: {submission_id!r}")
    image = _required_string(data, "image")
    if not IMAGE_DIGEST.fullmatch(image):
        raise ChallengePackError("submission image must use an immutable @sha256 digest")
    source_revision = _required_string(data, "source_revision")
    adapter_api = _required_string(data, "adapter_api")
    if adapter_api != SUBMISSION_API:
        raise ChallengePackError(f"adapter_api must be {SUBMISSION_API!r}")
    config_sha256 = _required_string(data, "config_sha256").lower()
    if not SHA256.fullmatch(config_sha256):
        raise ChallengePackError("config_sha256 must be a lowercase or uppercase SHA256 digest")
    network = _required_string(data, "network")
    if network not in {"none", "model-only"}:
        raise ChallengePackError("submission network must be 'none' or 'model-only'")
    raw_entrypoint = data.get("entrypoint")
    if not isinstance(raw_entrypoint, list) or not raw_entrypoint:
        raise ChallengePackError("submission entrypoint must be a non empty list")
    if any(not isinstance(part, str) or not part for part in raw_entrypoint):
        raise ChallengePackError("submission entrypoint must contain non empty strings")
    return ChallengeSubmission(
        submission_id=submission_id,
        image=image,
        source_revision=source_revision,
        adapter_api=adapter_api,
        config_sha256=config_sha256,
        network=network,
        entrypoint=tuple(raw_entrypoint),
    )


def build_execution_plan(
    pack: ChallengePack, submission: ChallengeSubmission, task_id: str
) -> ChallengeExecutionPlan:
    """Build one restricted mount plan without exposing another task's private inputs."""

    task = next((candidate for candidate in pack.tasks if candidate.task_id == task_id), None)
    if task is None:
        raise ChallengePackError(f"unknown challenge task id: {task_id!r}")

    fixture_source = task.fixture.relative_to(pack.root).as_posix()
    prompt_source = task.prompt.relative_to(pack.root).as_posix()

    mounts = (
        {
            "name": "fixture",
            "source": fixture_source,
            "target": "/challenge/task",
            "read_only": True,
        },
        {
            "name": "prompt",
            "source": prompt_source,
            "target": "/challenge/prompt.txt",
            "read_only": True,
        },
        {
            "name": "corpus",
            "source": pack.corpus.relative_to(pack.root).as_posix(),
            "target": "/challenge/corpus",
            "read_only": True,
        },
        {
            "name": "output",
            "source": f"output/{submission.submission_id}/{task_id}",
            "target": "/challenge/output",
            "read_only": False,
        },
    )
    security = {
        "read_only_root": True,
        "cap_drop": ["ALL"],
        "no_new_privileges": True,
        "cross_task_inputs_mounted": False,
        "private_evaluator_mounted": False,
        "oracle_mounted": False,
        "reference_mounted": False,
        "host_credentials_mounted": False,
    }
    return ChallengeExecutionPlan(
        submission_id=submission.submission_id,
        image=submission.image,
        network=submission.network,
        task_id=task_id,
        mounts=mounts,
        security=security,
        entrypoint=submission.entrypoint,
    )
