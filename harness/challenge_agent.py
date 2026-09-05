"""Run the evaluator owned fixed agent command with an explicit task environment."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .challenge_evaluator import ChallengeTaskContext
from .challenge_protocol import ADAPTER_API
from .checker_run import Completed, run_bounded

DEFAULT_AGENT_TIMEOUT_SECONDS = 15 * 60
RESERVED_AGENT_ENV = frozenset(
    {
        "AMB_CHALLENGE_API",
        "AMB_AGENT_PROTOCOL",
        "AMB_TASK_ID",
        "AMB_TASK_FIXTURE",
        "AMB_TASK_PROMPT",
        "AMB_TASK_OUTPUT",
        "AMB_ADAPTER_SOCKET",
    }
)


class ChallengeAgentError(RuntimeError):
    """The fixed agent command was invalid or did not complete successfully."""


@dataclass(frozen=True)
class ChallengeAgentRunResult:
    """Bounded process result for one fixed agent task."""

    task_id: str
    returncode: int | None
    timed_out: bool
    wall_s: float
    stdout: str
    stderr: str

    @classmethod
    def from_completed(cls, task_id: str, completed: Completed) -> "ChallengeAgentRunResult":
        return cls(
            task_id=task_id,
            returncode=completed.returncode,
            timed_out=completed.timed_out,
            wall_s=completed.wall_s,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def _command_env(
    context: ChallengeTaskContext,
    extra_env: Mapping[str, str] | None,
) -> dict[str, str]:
    """Build the only task and adapter values injected into the fixed agent process."""

    env = {
        "AMB_CHALLENGE_API": ADAPTER_API,
        "AMB_AGENT_PROTOCOL": "search-only-adapter",
        "AMB_TASK_ID": context.task_id,
        "AMB_TASK_FIXTURE": str(context.fixture),
        "AMB_TASK_PROMPT": str(context.prompt),
        "AMB_TASK_OUTPUT": str(context.output),
        "AMB_ADAPTER_SOCKET": str(context.adapter.socket_path),
    }
    if extra_env:
        reserved = RESERVED_AGENT_ENV.intersection(extra_env)
        if reserved:
            raise ChallengeAgentError(
                f"fixed agent configuration cannot override reserved variables: {sorted(reserved)}"
            )
        env.update(extra_env)
    return env


def run_fixed_agent_command(
    command: Sequence[str],
    context: ChallengeTaskContext,
    *,
    timeout_seconds: float = DEFAULT_AGENT_TIMEOUT_SECONDS,
    extra_env: Mapping[str, str] | None = None,
) -> ChallengeAgentRunResult:
    """Run one fixed agent command without a shell and bound its complete process tree."""

    if not command or any(not isinstance(part, str) or not part for part in command):
        raise ChallengeAgentError("fixed agent command must be a non empty argument list")
    if timeout_seconds <= 0:
        raise ChallengeAgentError("fixed agent timeout must be positive")
    completed = run_bounded(
        list(command),
        cwd=context.output,
        timeout_s=timeout_seconds,
        env=_command_env(context, extra_env),
    )
    return ChallengeAgentRunResult.from_completed(context.task_id, completed)


def make_command_agent_runner(
    command: Sequence[str],
    *,
    timeout_seconds: float = DEFAULT_AGENT_TIMEOUT_SECONDS,
    extra_env: Mapping[str, str] | None = None,
):
    """Return an evaluator callback that converts a command failure into a failed task."""

    frozen_command = tuple(command)

    def run(context: ChallengeTaskContext) -> None:
        result = run_fixed_agent_command(
            frozen_command,
            context,
            timeout_seconds=timeout_seconds,
            extra_env=extra_env,
        )
        if not result.ok:
            state = "timed out" if result.timed_out else f"returned {result.returncode}"
            raise ChallengeAgentError(f"fixed agent {state}")

    return run
