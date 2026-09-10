"""Validate a challenge submission descriptor and print its restricted execution plan.

    python -m scripts.validate_challenge_submission \
        --pack /private/amb-challenge-pack --submission submission.json

This command performs no image pull, import, model call or submission execution.
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        pack = load_private_pack(args.pack)
        submission = load_submission(args.submission)
        plans = [build_execution_plan(pack, submission, task.task_id) for task in pack.tasks]
    except ChallengePackError as error:
        print(f"invalid challenge evaluation input: {error}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps([plan.to_dict() for plan in plans], indent=2))
    else:
        print(
            f"valid submission {submission.submission_id!r}: "
            f"image {submission.image}, {len(pack.tasks)} task(s), network {submission.network!r}"
        )
        print("execution plan mounts no private evaluator, oracle, reference or host credential")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
