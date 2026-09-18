"""Verify a sequence plan and held out manifest before a run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness.frozen_manifest import FrozenEvaluationManifest
from harness.sequence_plan import load_plan_file
from harness.sequence_preflight import validate_sequence_evaluation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--tasks-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    plan = load_plan_file(args.plan)
    manifest = FrozenEvaluationManifest.load(args.manifest, root=args.repo_root)
    result = validate_sequence_evaluation(
        plan,
        manifest,
        repo_root=args.repo_root,
        tasks_root=args.tasks_root or args.repo_root / "tasks",
    ).to_dict()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
