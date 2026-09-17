"""Freeze and verify a held out evaluation manifest before vendor measurement."""

from __future__ import annotations

import argparse
from pathlib import Path

from harness.frozen_manifest import FrozenEvaluationManifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--corpus-file", action="append", required=True)
    parser.add_argument("--protocol-file", action="append", required=True)
    args = parser.parse_args()

    manifest = FrozenEvaluationManifest.build(
        args.repo_root,
        manifest_id=args.manifest_id,
        created_at=args.created_at,
        corpus_files=args.corpus_file,
        protocol_files=args.protocol_file,
    )
    manifest.write(args.output)
    print(f"wrote frozen heldout manifest {args.output} with digest {manifest.digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
