"""Check all machine verifiable AMB challenge release gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_readiness import evaluate_readiness, readiness_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--rules", required=True, type=Path)
    parser.add_argument("--release", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--deliberately-bad", type=Path)
    parser.add_argument("--red-team-report", type=Path)
    parser.add_argument("--roster-review", type=Path)
    parser.add_argument("--public-smoke-report", type=Path)
    parser.add_argument("--evaluator-revision")
    args = parser.parse_args()
    result = readiness_result(
        evaluate_readiness(
            args.pack,
            args.policy,
            args.rules,
            release_path=args.release,
            baseline_path=args.baseline,
            deliberately_bad_path=args.deliberately_bad,
            red_team_report_path=args.red_team_report,
            roster_review_path=args.roster_review,
            public_smoke_report_path=args.public_smoke_report,
            evaluator_revision=args.evaluator_revision,
        )
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
