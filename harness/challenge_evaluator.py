"""Coordinate one fixed agent run, one memory sidecar and one private checker per task."""

from __future__ import annotations

import math
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
    _reject_output_overlap,
    _reject_runtime_overlap,
    _reject_shared_root_overlap,
    start_challenge_adapter,
)
from .challenge_scoring import ChallengeTaskScore, build_score_manifest, run_private_checker

DEFAULT_ADAPTER_CALL_BUDGET = 128


class ChallengeEvaluatorError(RuntimeError):
    """The fixed evaluator could not complete a task without changing its semantics."""


@dataclass(frozen=True)
class ChallengeTaskContext:
    """The current task inputs and adapter socket exposed to the fixed agent runner."""

    task_id: str
    fixture: Path
    prompt: Path
    output: Path
    adapter: ChallengeAgentAdapter


AgentRunner = Callable[[ChallengeTaskContext], None]


@dataclass
class ChallengeAdapterClient:
    """Small fixed evaluator client for one sidecar socket."""

    socket_path: Path
    task_id: str
    max_calls: int = DEFAULT_ADAPTER_CALL_BUDGET
    _sequence: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.max_calls, bool) or not isinstance(self.max_calls, int) or self.max_calls <= 0:
            raise ChallengeEvaluatorError("adapter call budget must be a positive integer")

    def _request(self, method: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if self._sequence >= self.max_calls:
            raise ChallengeEvaluatorError("adapter call budget exceeded")
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


@dataclass(frozen=True)
class ChallengeAgentAdapter:
    """Search-only adapter view exposed to the fixed task agent."""

    _client: ChallengeAdapterClient

    @property
    def socket_path(self) -> Path:
        """Return the socket path for the evaluator command runner."""

        return self._client.socket_path

    def search(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        return self._client.search(query, limit=limit)


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
    if output.exists():
        if not output.is_dir():
            raise ChallengeEvaluatorError(f"task output path is not a directory: {output}")
        if any(output.iterdir()):
            raise ChallengeEvaluatorError(f"task output directory must start empty: {output}")
    else:
        output.mkdir(parents=True, exist_ok=True)
    return task.fixture, task.prompt, output


def _failed_task_score(task: ChallengeTask, verdict: str) -> ChallengeTaskScore:
    return ChallengeTaskScore(
        task_id=task.task_id,
        passed=False,
        verdict=verdict,
        checker_returncode=None,
        checker_timed_out=False,
        checker_wall_s=0.0,
    )


def evaluate_submission(
    pack: ChallengePack,
    submission: ChallengeSubmission,
    output_root: str | Path,
    runtime_root: str | Path,
    agent_runner: AgentRunner,
    *,
    checker_timeout_s: float = DEFAULT_TIMEOUT_SECONDS,
    pack_digest: str,
    rules_digest: str,
    evaluator_revision: str,
    model_proxy_socket: str | Path | None = None,
    adapter_call_budget: int = DEFAULT_ADAPTER_CALL_BUDGET,
) -> tuple[dict[str, Any], list[ChallengeTaskScore]]:
    """Run every task with fixed sequencing and return public and private score manifests.

    ``agent_runner`` is supplied by the evaluator and must use the context's current task paths
    and adapter socket. It must not receive the pack root, checker, oracle or reference paths.
    """

    if (
        isinstance(adapter_call_budget, bool)
        or not isinstance(adapter_call_budget, int)
        or adapter_call_budget <= 0
    ):
        raise ChallengeEvaluatorError("adapter call budget must be a positive integer")
    if (
        isinstance(checker_timeout_s, bool)
        or not isinstance(checker_timeout_s, (int, float))
        or not math.isfinite(checker_timeout_s)
        or checker_timeout_s <= 0
    ):
        raise ChallengeEvaluatorError("checker timeout must be finite and positive")
    try:
        output_base = _reject_output_overlap(Path(output_root), pack)
        runtime_base = _reject_runtime_overlap(Path(runtime_root), pack)
        _reject_shared_root_overlap(output_base, runtime_base)
    except ChallengeRunnerError as error:
        raise ChallengeEvaluatorError(f"invalid evaluator roots: {error}") from error
    scores: list[ChallengeTaskScore] = []
    for task in pack.tasks:
        task_runtime = runtime_base / task.task_id
        fixture, prompt, output = _task_paths(task, output_base, submission.submission_id)
        handle: ChallengeAdapterHandle | None = None
        task_failure: str | None = None
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
            client = ChallengeAdapterClient(
                handle.socket_path,
                task.task_id,
                max_calls=adapter_call_budget,
            )
            client.reset()
            context = ChallengeTaskContext(
                task_id=task.task_id,
                fixture=fixture,
                prompt=prompt,
                output=output,
                adapter=ChallengeAgentAdapter(client),
            )
            try:
                agent_runner(context)
            except Exception as error:  # noqa: BLE001 - a fixed agent failure is a failed task
                task_failure = f"fixed agent failed: {type(error).__name__}: {error}"
        except ChallengeEvaluatorError as error:
            task_failure = str(error)
        except ChallengeRunnerError as error:
            raise ChallengeEvaluatorError(f"sidecar failed for {task.task_id!r}: {error}") from error
        finally:
            if handle is not None:
                handle.stop()
        if task_failure is not None:
            scores.append(_failed_task_score(task, task_failure))
            continue
        score = run_private_checker(task, output, timeout_s=checker_timeout_s)
        scores.append(score)

    public = build_score_manifest(
        pack,
        submission,
        scores,
        pack_digest=pack_digest,
        rules_digest=rules_digest,
        evaluator_revision=evaluator_revision,
        public=True,
    )
    private = build_score_manifest(
        pack,
        submission,
        scores,
        pack_digest=pack_digest,
        rules_digest=rules_digest,
        evaluator_revision=evaluator_revision,
        public=False,
    )
    return public, private
