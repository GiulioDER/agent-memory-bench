"""Verify that a baseline manifest beats a deliberately bad adapter manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_baselines import ChallengeBaselineError, verify_baseline_ordering  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--deliberately-bad", required=True, type=Path)
    parser.add_argument("--minimum-margin", type=float, default=0.0)
    args = parser.parse_args()
    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        deliberately_bad = json.loads(args.deliberately_bad.read_text(encoding="utf-8"))
        result = verify_baseline_ordering(
            baseline,
            deliberately_bad,
            minimum_margin=args.minimum_margin,
        )
    except (OSError, json.JSONDecodeError, ChallengeBaselineError) as error:
        print(f"challenge ordering failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
