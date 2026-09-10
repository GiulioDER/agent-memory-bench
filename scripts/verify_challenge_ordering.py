"""Verify that a baseline manifest beats a deliberately bad adapter manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_baselines import ChallengeBaselineError, verify_baseline_ordering
from harness.challenge_pack import ChallengePackError, load_private_pack
from harness.challenge_policy import ChallengePolicyError, load_policy
from harness.challenge_release import current_evaluator_revision, hash_private_pack
from harness.challenge_rules import ChallengeRulesError, load_rules, rules_digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--deliberately-bad", required=True, type=Path)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--rules", required=True, type=Path)
    parser.add_argument("--evaluator-revision", required=True)
    parser.add_argument("--minimum-margin", type=float, default=0.0)
    args = parser.parse_args()
    try:
        if current_evaluator_revision(REPO) != args.evaluator_revision:
            raise ChallengeBaselineError(
                "evaluator revision does not match the checked out evaluator source"
            )
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        deliberately_bad = json.loads(args.deliberately_bad.read_text(encoding="utf-8"))
        pack = load_private_pack(args.pack)
        policy = load_policy(args.policy, require_frozen=True)
        rules = load_rules(args.rules, require_final=True)
        result = verify_baseline_ordering(
            baseline,
            deliberately_bad,
            minimum_margin=args.minimum_margin,
            expected_pack_id=pack.manifest["pack_id"],
            expected_pack_digest=hash_private_pack(pack),
            expected_rules_digest=rules_digest(rules),
            expected_policy_digest=policy.digest(),
            expected_scoring_version=pack.manifest["scoring_version"],
            expected_evaluator_revision=args.evaluator_revision,
            expected_task_ids=(task.task_id for task in pack.tasks),
        )
    except (
        OSError,
        json.JSONDecodeError,
        ChallengeBaselineError,
        ChallengePackError,
        ChallengePolicyError,
        ChallengeRulesError,
    ) as error:
        print(f"challenge ordering failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
