"""Run trusted private checkers after a sidecar task and build score manifests."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .challenge_pack import ChallengePack, ChallengeSubmission, ChallengeTask
from .checker_run import DEFAULT_TIMEOUT_S, run_bounded


class ChallengeScoringError(RuntimeError):
    """The private checker boundary or score manifest is invalid."""


@dataclass(frozen=True)
class ChallengeTaskScore:
    task_id: str
    passed: bool
    verdict: str
    checker_returncode: int | None
    checker_timed_out: bool
    checker_wall_s: float

    def private_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "verdict": self.verdict,
            "checker_returncode": self.checker_returncode,
            "checker_timed_out": self.checker_timed_out,
        }

    def public_dict(self) -> dict[str, Any]:
        """Return task outcome data without a checker message that may reveal private facts."""

        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "checker_returncode": self.checker_returncode,
            "checker_timed_out": self.checker_timed_out,
        }


def _checker_command(task: ChallengeTask, workdir: Path) -> list[str]:
    wrapper = Path(__file__).resolve().parents[1] / "scripts" / "run_private_checker.py"
    return [
        sys.executable,
        str(wrapper),
        "--task-id",
        task.task_id,
        "--checker",
        str(task.checker),
        "--workdir",
        str(workdir),
        "--oracle",
        str(task.oracle),
    ]


def run_private_checker(
    task: ChallengeTask,
    workdir: str | Path,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> ChallengeTaskScore:
    """Run a private checker in a bounded subprocess after the entrant container exits."""

    if (
        isinstance(timeout_s, bool)
        or not isinstance(timeout_s, (int, float))
        or not math.isfinite(timeout_s)
        or timeout_s <= 0
    ):
        raise ChallengeScoringError("checker timeout must be finite and positive")
    sandbox = Path(workdir).expanduser().resolve()
    if not sandbox.is_dir() or sandbox.is_symlink():
        raise ChallengeScoringError(f"checker workdir is not a regular directory: {sandbox}")
    completed = run_bounded(_checker_command(task, sandbox), cwd=sandbox, timeout_s=timeout_s)
    if completed.timed_out:
        return ChallengeTaskScore(
            task_id=task.task_id,
            passed=False,
            verdict="checker timed out",
            checker_returncode=None,
            checker_timed_out=True,
            checker_wall_s=completed.wall_s,
        )
    if completed.returncode != 0:
        raise ChallengeScoringError(
            f"private checker wrapper failed for {task.task_id!r}: {completed.stderr[-500:]}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ChallengeScoringError(
            f"private checker wrapper returned invalid JSON for {task.task_id!r}"
        ) from error
    if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
        raise ChallengeScoringError(f"private checker returned an invalid result for {task.task_id!r}")
    if payload.get("task_id") != task.task_id:
        raise ChallengeScoringError(f"private checker returned the wrong task id for {task.task_id!r}")
    verdict = payload.get("verdict")
    if not isinstance(verdict, str):
        raise ChallengeScoringError(f"private checker returned a non string verdict for {task.task_id!r}")
    return ChallengeTaskScore(
        task_id=task.task_id,
        passed=payload["ok"],
        verdict=verdict,
        checker_returncode=0,
        checker_timed_out=False,
        checker_wall_s=completed.wall_s,
    )


def build_score_manifest(
    pack: ChallengePack,
    submission: ChallengeSubmission,
    scores: list[ChallengeTaskScore] | tuple[ChallengeTaskScore, ...],
    *,
    public: bool = False,
) -> dict[str, Any]:
    """Build a deterministic aggregate manifest from one score per private task."""

    by_task = {score.task_id: score for score in scores}
    expected = {task.task_id for task in pack.tasks}
    if set(by_task) != expected or len(by_task) != len(scores):
        raise ChallengeScoringError(
            "score manifest needs exactly one result for every private challenge task"
        )
    rows = [
        by_task[task.task_id].public_dict() if public else by_task[task.task_id].private_dict()
        for task in pack.tasks
    ]
    passed = sum(row["passed"] for row in rows)
    manifest: dict[str, Any] = {
        "schema": 1,
        "kind": "amb-challenge-score-manifest",
        "pack_id": pack.manifest["pack_id"],
        "scoring_version": pack.manifest["scoring_version"],
        "submission_id": submission.submission_id,
        "image": submission.image,
        "task_count": len(rows),
        "passed_count": passed,
        "score": passed / len(rows),
        "tasks": rows,
        "private_details_included": not public,
    }
    return manifest


def write_score_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    """Create or repeat an identical score manifest without allowing replacement data."""

    target = Path(path).expanduser()
    if target.exists() and target.is_symlink():
        raise ChallengeScoringError(f"score manifest target must not be a symlink: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if target.exists():
        if not target.is_file():
            raise ChallengeScoringError(f"score manifest target is not a regular file: {target}")
        if target.read_text(encoding="utf-8") == content:
            return
        raise ChallengeScoringError(f"score manifest target already contains different data: {target}")
    try:
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as error:
        if target.is_symlink() or not target.is_file():
            raise ChallengeScoringError(f"score manifest target is not a regular file: {target}") from error
        if target.read_text(encoding="utf-8") == content:
            return
        raise ChallengeScoringError(f"score manifest target already contains different data: {target}") from error
