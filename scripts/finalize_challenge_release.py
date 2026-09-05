"""Validate and hash an external private AMB challenge pack and frozen policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_pack import ChallengePackError, load_private_pack  # noqa: E402
from harness.challenge_policy import ChallengePolicyError, load_policy  # noqa: E402
from harness.challenge_release import build_release_manifest, write_release_manifest  # noqa: E402
from harness.challenge_rules import ChallengeRulesError, load_rules  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--rules", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        pack = load_private_pack(args.pack)
        policy = load_policy(args.policy)
        rules = load_rules(args.rules, require_final=True)
        if "TO_BE_" in policy.model_id or "TO_BE_" in policy.provider_id:
            raise ChallengePolicyError("final release policy contains unresolved placeholders")
        manifest = build_release_manifest(pack, policy, rules)
        write_release_manifest(args.output, manifest)
    except (ChallengePackError, ChallengePolicyError, ChallengeRulesError, OSError, ValueError) as error:
        print(f"challenge release failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
