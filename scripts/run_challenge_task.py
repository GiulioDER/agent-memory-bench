"""Dry run or execute one isolated AMB challenge task.

Dry run:
    python -m scripts.run_challenge_task --pack /private/amb-pack \
        --submission submission.json --task heldout-task-001 --output-root /private/amb-output

Execution requires the explicit ``--execute`` flag. The image must already be available locally;
the runner uses ``--pull=never``. A model-only entry additionally requires an evaluator-managed
model proxy socket and still runs with the container network disabled.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_pack import (
    ChallengePackError,
    build_execution_plan,
    load_private_pack,
    load_submission,
)
from harness.challenge_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    ChallengeRunnerError,
    build_docker_argv,
    run_challenge_task,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--task", required=True, dest="task_id")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--model-proxy-socket", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    try:
        pack = load_private_pack(args.pack)
        submission = load_submission(args.submission)
        plan = build_execution_plan(pack, submission, args.task_id)
        if not args.execute:
            argv = build_docker_argv(
                pack,
                plan,
                args.output_root,
                container_name="amb-challenge-dry-run",
                model_proxy_socket=args.model_proxy_socket,
            )
            print(json.dumps({"executed": False, "argv": argv}, indent=2))
            return 0
        result = run_challenge_task(
            pack,
            submission,
            args.task_id,
            args.output_root,
            timeout_seconds=args.timeout_seconds,
            model_proxy_socket=args.model_proxy_socket,
        )
    except (ChallengePackError, ChallengeRunnerError) as error:
        print(f"invalid challenge run: {error}", file=sys.stderr)
        return 1

    print(json.dumps({"executed": True, **result.to_dict()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
