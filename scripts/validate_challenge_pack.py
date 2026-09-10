"""Validate one private AMB challenge evaluation pack without running a submission.

    python -m scripts.validate_challenge_pack --pack C:/private/amb-challenge-pack

The command checks the pack marker, private visibility, task paths, path containment, regular
files and symlink absence. It deliberately does not execute the pack or any submitted code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.challenge_pack import ChallengePackError, load_private_pack
from harness.challenge_pack_audit import ChallengePackLeakageError, audit_pack_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        pack = load_private_pack(args.pack)
        leakage = audit_pack_corpus(pack)
    except (ChallengePackError, ChallengePackLeakageError) as error:
        print(f"invalid private challenge pack: {error}", file=sys.stderr)
        return 1

    if args.as_json:
        print(
            json.dumps(
                {
                    "pack_id": pack.manifest["pack_id"],
                    "scoring_version": pack.manifest["scoring_version"],
                    "tasks": [task.task_id for task in pack.tasks],
                    "corpus_audit": leakage.to_dict(),
                },
                indent=2,
            )
        )
    else:
        print(
            f"valid private challenge pack {pack.manifest['pack_id']!r}: "
            f"{len(pack.tasks)} task(s), scoring {pack.manifest['scoring_version']}, "
            f"corpus audit {leakage.to_dict()['status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
