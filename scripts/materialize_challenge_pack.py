"""Copy and validate an organizer supplied external AMB private pack source."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_pack_builder import ChallengePackBuildError, materialize_private_pack  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    try:
        pack = materialize_private_pack(args.source, args.destination)
    except (ChallengePackBuildError, OSError, ValueError) as error:
        print(f"private pack materialization failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "pass",
                "pack_id": pack.manifest["pack_id"],
                "destination": str(pack.root),
                "task_count": len(pack.tasks),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
