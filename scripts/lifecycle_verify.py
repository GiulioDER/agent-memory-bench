"""Verify and score the optional lifecycle temporal capability artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harness.lifecycle import (
    load_lifecycle_artifact,
    load_lifecycle_manifest,
    score_lifecycle_artifact,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = load_lifecycle_manifest(args.manifest)
        header, rows = load_lifecycle_artifact(args.artifact, manifest)
        report = score_lifecycle_artifact(manifest, header, rows)
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"lifecycle verification failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["qualification"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
