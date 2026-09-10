"""Validate a fresh-machine public AMB smoke report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_smoke import ChallengeSmokeError, validate_public_smoke_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--repository-revision")
    args = parser.parse_args()
    try:
        report = validate_public_smoke_report(
            json.loads(args.report.read_text(encoding="utf-8")),
            expected_repository_revision=args.repository_revision,
        )
    except (ChallengeSmokeError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"invalid challenge public smoke report: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "repository_revision": report["repository_revision"],
                "status": "pass",
                "tests_passed": report["tests_passed"],
                "tests_skipped": report["tests_skipped"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
