"""Run every private AMB challenge task with one fixed evaluator agent command.

Example:
    python -m scripts.evaluate_challenge --pack /private/amb-pack \
        --submission submission.json --output-root /private/amb-output \
        --runtime-root /private/amb-runtime --public-manifest public.json \
        --private-manifest private.json --agent-command \
        "python /evaluator/fixed_agent.py"

The agent command is supplied by the evaluator, not by an entrant image. It receives explicit
task and adapter environment variables and runs without a shell under a bounded process tree.
Provider credentials must be injected through the evaluator's approved environment policy, never
through the submission descriptor.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_agent import (  # noqa: E402
    DEFAULT_AGENT_TIMEOUT_SECONDS,
    make_command_agent_runner,
)
from harness.challenge_evaluator import (  # noqa: E402
    DEFAULT_ADAPTER_CALL_BUDGET,
    ChallengeEvaluatorError,
    evaluate_submission,
)
from harness.challenge_pack import ChallengePackError, load_private_pack, load_submission  # noqa: E402
from harness.challenge_runner import DEFAULT_TIMEOUT_SECONDS  # noqa: E402
from harness.challenge_scoring import ChallengeScoringError, write_score_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--public-manifest", required=True, type=Path)
    parser.add_argument("--private-manifest", required=True, type=Path)
    parser.add_argument("--agent-command", required=True)
    parser.add_argument("--agent-timeout-seconds", type=float, default=DEFAULT_AGENT_TIMEOUT_SECONDS)
    parser.add_argument("--checker-timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--adapter-call-budget", type=int, default=DEFAULT_ADAPTER_CALL_BUDGET)
    parser.add_argument("--model-proxy-socket", type=Path)
    args = parser.parse_args()

    try:
        command = shlex.split(args.agent_command, posix=True)
        if not command:
            raise ChallengeEvaluatorError("agent command must not be empty")
        pack = load_private_pack(args.pack)
        submission = load_submission(args.submission)
        public, private = evaluate_submission(
            pack,
            submission,
            args.output_root,
            args.runtime_root,
            make_command_agent_runner(command, timeout_seconds=args.agent_timeout_seconds),
            checker_timeout_s=args.checker_timeout_seconds,
            model_proxy_socket=args.model_proxy_socket,
            adapter_call_budget=args.adapter_call_budget,
        )
        write_score_manifest(args.public_manifest, public)
        write_score_manifest(args.private_manifest, private)
    except (ChallengePackError, ChallengeEvaluatorError, ChallengeScoringError) as error:
        print(f"challenge evaluation failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(public, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
