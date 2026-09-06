"""Validate an independent task roster review against one private AMB pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_pack import ChallengePackError, load_private_pack
from harness.challenge_release import hash_private_pack
from harness.challenge_roster import ChallengeRosterReviewError, validate_roster_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--review", required=True, type=Path)
    args = parser.parse_args()
    try:
        pack = load_private_pack(args.pack)
        data = json.loads(args.review.read_text(encoding="utf-8"))
        review = validate_roster_review(
            data,
            expected_pack_digest=hash_private_pack(pack),
            expected_task_ids=(task.task_id for task in pack.tasks),
            expected_pack_preparer_id=pack.manifest.get("prepared_by"),
        )
    except (
        ChallengePackError,
        ChallengeRosterReviewError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"invalid challenge roster review: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "pass",
                "pack_id": pack.manifest["pack_id"],
                "task_count": len(pack.tasks),
                "reviewer_id": review["reviewer_id"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
