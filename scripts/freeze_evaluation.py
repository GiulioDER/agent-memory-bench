"""Freeze and verify a held out evaluation manifest before vendor measurement."""

from __future__ import annotations

import argparse
from pathlib import Path

from harness.frozen_manifest import FrozenEvaluationManifest
from harness.sequence_plan import load_plan_file
from harness.sequence_validation import sequence_input_files, validate_plan


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--corpus-file", action="append", required=True)
    parser.add_argument("--protocol-file", action="append", required=True)
    parser.add_argument("--sequence-plan", type=Path)
    parser.add_argument("--tasks-root", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    protocol_files = list(args.protocol_file)
    if args.sequence_plan:
        sequence_plan_path = (
            args.sequence_plan
            if args.sequence_plan.is_absolute()
            else repo_root / args.sequence_plan
        )
        plan = load_plan_file(sequence_plan_path)
        tasks_root_arg = args.tasks_root or Path("tasks")
        tasks_root = (
            tasks_root_arg
            if tasks_root_arg.is_absolute()
            else repo_root / tasks_root_arg
        ).resolve()
        validate_plan(plan, tasks_root=tasks_root)
        protocol_files.extend(
            sequence_input_files(plan, repo_root=repo_root, tasks_root=tasks_root)
        )

    manifest = FrozenEvaluationManifest.build(
        repo_root,
        manifest_id=args.manifest_id,
        created_at=args.created_at,
        corpus_files=args.corpus_file,
        protocol_files=_unique(protocol_files),
    )
    manifest.write(args.output)
    print(f"wrote frozen heldout manifest {args.output} with digest {manifest.digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
