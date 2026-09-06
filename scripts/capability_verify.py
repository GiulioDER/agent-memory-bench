"""Verify and score a temporal or tenant isolation capability artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harness.capabilities import load_artifact, load_manifest, qualification_subset, score_artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument(
        "--standard-subset",
        type=Path,
        help="score only the fixed qualification subset selected from the manifest",
    )
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
        if args.standard_subset:
            manifest = qualification_subset(manifest, args.standard_subset)
        _, rows = load_artifact(args.artifact, manifest)
        report = score_artifact(manifest, rows)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"capability verification failed: {error}", file=sys.stderr)
        return 2

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.qualification["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
