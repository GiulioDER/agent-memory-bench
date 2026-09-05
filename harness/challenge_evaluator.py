"""Coordinate one fixed agent run, one memory sidecar and one private checker per task."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .challenge_pack import ChallengePack, ChallengeSubmission, ChallengeTask
from .challenge_protocol import ChallengeProtocolError, request_unix_socket
from .challenge_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    ChallengeAdapterHandle,
    ChallengeRunnerError,
    start_challenge_adapter,
)
from .challenge_scoring import ChallengeTaskScore, build_score_manifest, run_private_checker


class ChallengeEvaluatorError(RuntimeError):
    """The fixed evaluator could not complete a task without changing its semantics."""


@dataclass(frozen=True)
class ChallengeTaskContext:
    """The current task inputs and adapter socket exposed to the fixed agent runner."""

    task_id: str
    fixture: Path
    prompt: Path
    output: Path
    adapter_socket: Path
    adapter: "ChallengeAdapterClient"


AgentRunner = Callable[[ChallengeTaskContext], None]


@dataclass
class ChallengeAdapterClient:
    """Small fixed evaluator client for one sidecar socket."""

    socket_path: Path
    task_id: str
    _sequence: int = 0

    def _request(self, method: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._sequence += 1
        try:
            response = request_unix_socket(
                str(self.socket_path),
                f"{self.task_id}-{self._sequence}",
                method,
                params,
            )
        except ChallengeProtocolError as error:
            raise ChallengeEvaluatorError(f"adapter {method} protocol error: {error}") from error
        if not response.get("ok"):
            error = response.get("error", {})
            raise ChallengeEvaluatorError(f"adapter {method} failed: {error}")
        return response["result"]

    def health(self) -> dict[str, Any]:
        return self._request("health")

    def search(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        return self._request(
            "search",
            {"task_id": self.task_id, "query": query, "limit": limit},
        )

    def reset(self) -> dict[str, Any]:
        return self._request("reset", {"task_id": self.task_id})


def _task_paths(
    task: ChallengeTask,
    output_root: Path,
    submission_id: str,
) -> tuple[Path, Path, Path]:
    output = output_root / submission_id / task.task_id
    current = output
    while current != output_root:
        if current.exists() and current.is_symlink():
            raise ChallengeEvaluatorError(f"task output path must not contain a symlink: {current}")
        current = current.parent
    output.mkdir(parents=True, exist_ok=True)
    return task.fixture, task.prompt, output


def evaluate_submission(
    pack: ChallengePack,
    submission: ChallengeSubmission,
    output_root: str | Path,
    runtime_root: str | Path,
    agent_runner: AgentRunner,
    *,
    checker_timeout_s: float = DEFAULT_TIMEOUT_SECONDS,
    model_proxy_socket: str | Path | None = None,
) -> tuple[dict[str, Any], list[ChallengeTaskScore]]:
    """Run every task with fixed sequencing and return public and private score manifests.

    ``agent_runner`` is supplied by the evaluator and must use the context's current task paths
    and adapter socket. It must not receive the pack root, checker, oracle or reference paths.
    """

    raw_output_base = Path(output_root).expanduser()
    raw_runtime_base = Path(runtime_root).expanduser()
    for root_name, root in (("output", raw_output_base), ("runtime", raw_runtime_base)):
        if root.exists() and root.is_symlink():
            raise ChallengeEvaluatorError(f"{root_name} root must not be a symlink: {root}")
    output_base = raw_output_base.resolve()
    runtime_base = raw_runtime_base.resolve()
    scores: list[ChallengeTaskScore] = []
    for task in pack.tasks:
        task_runtime = runtime_base / task.task_id
        fixture, prompt, output = _task_paths(task, output_base, submission.submission_id)
        handle: ChallengeAdapterHandle | None = None
        try:
            handle = start_challenge_adapter(
                pack,
                submission,
                task.task_id,
                output_base,
                task_runtime,
                model_proxy_socket=model_proxy_socket,
            )
            handle.wait_ready()
            client = ChallengeAdapterClient(handle.socket_path, task.task_id)
            client.reset()
            context = ChallengeTaskContext(
                task_id=task.task_id,
                fixture=fixture,
                prompt=prompt,
                output=output,
                adapter_socket=handle.socket_path,
                adapter=client,
            )
            agent_runner(context)
        except ChallengeRunnerError as error:
            raise ChallengeEvaluatorError(f"sidecar failed for {task.task_id!r}: {error}") from error
        finally:
            if handle is not None:
                handle.stop()
        score = run_private_checker(task, output, timeout_s=checker_timeout_s)
        scores.append(score)

    public = build_score_manifest(pack, submission, scores, public=True)
    private = build_score_manifest(pack, submission, scores, public=False)
    return public, private
