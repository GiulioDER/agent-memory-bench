"""Rank public challenge score manifests under the frozen private rules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_pack import ChallengePackError, load_private_pack
from harness.challenge_policy import ChallengePolicyError, load_policy
from harness.challenge_ranking import ChallengeRankingError, rank_challenge_entries
from harness.challenge_rules import ChallengeRulesError, load_rules


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--rules", required=True, type=Path)
    parser.add_argument("--manifest", required=True, action="append", type=Path)
    parser.add_argument("--evaluator-revision", required=True)
    args = parser.parse_args()
    try:
        pack = load_private_pack(args.pack)
        policy = load_policy(args.policy, require_frozen=True)
        rules = load_rules(args.rules, require_final=True)
        manifests = [json.loads(path.read_text(encoding="utf-8")) for path in args.manifest]
        result = rank_challenge_entries(
            manifests,
            rules,
            expected_pack_id=pack.manifest["pack_id"],
            expected_policy_digest=policy.digest(),
            expected_scoring_version=pack.manifest["scoring_version"],
            expected_evaluator_revision=args.evaluator_revision,
            expected_task_ids=tuple(task.task_id for task in pack.tasks),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ChallengePackError, ChallengePolicyError, ChallengeRulesError, ChallengeRankingError) as error:
        print(f"challenge ranking failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ranked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
