"""Build and execute the isolated Docker command for one AMB challenge task.

The runner is deliberately separate from pack validation and scoring. It runs one task at a time,
never pulls an image, never mounts the evaluator inputs, and never puts a checker in the entrant
container. The checker belongs to the evaluator process after the container exits.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .challenge_pack import (
    PUBLIC_REPO_ROOT,
    ChallengeExecutionPlan,
    ChallengePack,
    ChallengeSubmission,
    build_execution_plan,
)

DEFAULT_TIMEOUT_SECONDS = 15 * 60
MEMORY_LIMIT = "2g"
CPU_LIMIT = "2"
PIDS_LIMIT = "256"
NOFILE_LIMIT = "1024:1024"
TMPFS_SPEC = "/tmp:rw,noexec,nosuid,nodev,size=64m"


class ChallengeRunnerError(RuntimeError):
    """The evaluator could not prepare or start an isolated task run."""


@dataclass(frozen=True)
class ChallengeRunResult:
    task_id: str
    container_name: str
    returncode: int | None
    timed_out: bool
    duration_ms: float
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "container_name": self.container_name,
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "duration_ms": round(self.duration_ms, 3),
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def _reject_output_overlap(path: Path, pack: ChallengePack) -> Path:
    raw_output_root = path.expanduser()
    if raw_output_root.exists() and raw_output_root.is_symlink():
        raise ChallengeRunnerError(f"output root must not be a symlink: {raw_output_root}")
    output_root = raw_output_root.resolve()
    if output_root == PUBLIC_REPO_ROOT or PUBLIC_REPO_ROOT in output_root.parents:
        raise ChallengeRunnerError(
            f"output root is inside the public repository: {output_root}"
        )
    if output_root == pack.root or pack.root in output_root.parents:
        raise ChallengeRunnerError(f"output root is inside the private pack: {output_root}")
    return output_root


def _mount_source(
    pack: ChallengePack,
    plan: ChallengeExecutionPlan,
    mount: dict[str, Any],
    output_root: Path,
) -> Path:
    name = mount.get("name")
    if name == "output":
        source = output_root / plan.submission_id / plan.task_id
        current = source
        while current != output_root:
            if current.exists() and current.is_symlink():
                raise ChallengeRunnerError(f"mount {name!r} source uses a symlink: {current}")
            current = current.parent
    else:
        relative = mount.get("source")
        if not isinstance(relative, str) or not relative:
            raise ChallengeRunnerError(f"mount {name!r} has no relative source")
        source = pack.root.joinpath(*relative.split("/"))

    resolved = source.resolve()
    if name != "output":
        try:
            resolved.relative_to(pack.root)
        except ValueError as error:
            raise ChallengeRunnerError(f"mount {name!r} escapes the private pack") from error
    if name == "output" and not resolved.exists():
        return resolved
    if resolved.is_symlink() or not resolved.exists():
        raise ChallengeRunnerError(f"mount {name!r} source is not a regular pack path: {source}")
    return resolved


def _mount_arg(source: Path, target: str, *, read_only: bool) -> str:
    option = "readonly" if read_only else "rw"
    return f"type=bind,src={source},dst={target},{option}"


def build_docker_argv(
    pack: ChallengePack,
    plan: ChallengeExecutionPlan,
    output_root: str | Path,
    *,
    container_name: str,
    docker_binary: str = "docker",
    model_proxy_socket: str | Path | None = None,
) -> list[str]:
    """Build the fixed Docker argv for one validated task without executing it."""

    if not container_name or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-" for character in container_name):
        raise ChallengeRunnerError(f"invalid container name: {container_name!r}")
    output_base = _reject_output_overlap(Path(output_root), pack)
    argv = [
        docker_binary,
        "run",
        "--rm",
        "--pull=never",
        "--name",
        container_name,
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        f"--pids-limit={PIDS_LIMIT}",
        f"--memory={MEMORY_LIMIT}",
        f"--cpus={CPU_LIMIT}",
        f"--ulimit=nofile={NOFILE_LIMIT}",
        "--tmpfs",
        TMPFS_SPEC,
        "--network=none",
        "--workdir",
        "/challenge/task",
        "--env",
        f"AMB_TASK_ID={plan.task_id}",
    ]

    if plan.network == "model-only":
        if model_proxy_socket is None:
            raise ChallengeRunnerError(
                "model-only submissions require an evaluator-managed model proxy socket"
            )
        raw_proxy = Path(model_proxy_socket).expanduser()
        if raw_proxy.is_symlink():
            raise ChallengeRunnerError(f"model proxy socket must not be a symlink: {raw_proxy}")
        proxy = raw_proxy.resolve()
        if not proxy.exists():
            raise ChallengeRunnerError(f"model proxy socket is not a regular path: {proxy}")
        argv.extend(
            [
                "--mount",
                _mount_arg(proxy, "/challenge/model-proxy.sock", read_only=True),
                "--env",
                "AMB_MODEL_PROXY_SOCKET=/challenge/model-proxy.sock",
            ]
        )
    elif plan.network != "none":
        raise ChallengeRunnerError(f"unsupported challenge network: {plan.network!r}")

    for mount in plan.mounts:
        source = _mount_source(pack, plan, mount, output_base)
        target = mount.get("target")
        if not isinstance(target, str) or not target.startswith("/"):
            raise ChallengeRunnerError(f"mount {mount.get('name')!r} has an invalid target")
        argv.extend(
            [
                "--mount",
                _mount_arg(source, target, read_only=bool(mount.get("read_only"))),
            ]
        )

    if plan.network != "none":
        raise ChallengeRunnerError("network policy was not reduced to an isolated mode")
    argv.extend(["--entrypoint", plan.entrypoint[0], plan.image, *plan.entrypoint[1:]])
    return argv


def run_challenge_task(
    pack: ChallengePack,
    submission: ChallengeSubmission,
    task_id: str,
    output_root: str | Path,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    docker_binary: str = "docker",
    model_proxy_socket: str | Path | None = None,
) -> ChallengeRunResult:
    """Run one task with the fixed container policy and return its captured process result."""

    if timeout_seconds <= 0:
        raise ChallengeRunnerError("timeout_seconds must be positive")
    plan = build_execution_plan(pack, submission, task_id)
    output_base = _reject_output_overlap(Path(output_root), pack)
    task_output = output_base / submission.submission_id / task_id
    if task_output.exists() and task_output.is_symlink():
        raise ChallengeRunnerError(f"task output directory must not be a symlink: {task_output}")
    task_output.mkdir(parents=True, exist_ok=True)

    container_name = f"amb-challenge-{uuid.uuid4().hex}"
    argv = build_docker_argv(
        pack,
        plan,
        output_base,
        container_name=container_name,
        docker_binary=docker_binary,
        model_proxy_socket=model_proxy_socket,
    )
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        raise ChallengeRunnerError(f"could not start Docker: {error}") from error

    timed_out = False
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as error:
            timed_out = True
            subprocess.run(
                [docker_binary, "rm", "-f", container_name],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=30,
            )
            process.kill()
            stdout, stderr = process.communicate()
            stderr = f"{stderr}\nchallenge runner timeout after {timeout_seconds}s"
            if not stdout and error.stdout:
                stdout = error.stdout
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()

    return ChallengeRunResult(
        task_id=task_id,
        container_name=container_name,
        returncode=None if timed_out else process.returncode,
        timed_out=timed_out,
        duration_ms=(time.monotonic() - started) * 1000,
        stdout=stdout,
        stderr=stderr,
    )
