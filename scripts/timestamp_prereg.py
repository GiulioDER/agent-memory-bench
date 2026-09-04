"""Stamp or verify trusted timestamps for the preregistration directory.

Usage, from the repository root:

    python scripts/timestamp_prereg.py stamp
    python scripts/timestamp_prereg.py verify [--manifest PATH] [--strict]

``stamp`` writes an append-only hash manifest into ``preregistration/timestamps/`` and, when
the OpenTimestamps client is installed, anchors it against public calendars. The manifest is
a new uncommitted file, so the preregistration run guard will refuse to measure until it is
committed; commit and push it BEFORE the run, because the push is the first anchor whose
time is not ours to edit.

``verify`` reports MATCH / CHANGED / MISSING per stamped file. CHANGED is expected after
results are appended below a frozen prediction; the stamped bytes stay provable through the
recorded git blob. ``--strict`` turns any CHANGED into a failure, for checking a manifest
that should still match exactly (for example, immediately before a run starts). MISSING
always fails: preregistration files never legitimately disappear.

What an anchor proves, and what it deliberately does not claim: docs/TIMESTAMPING.md.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.timestamping import ots_stamp, stamp, verify

REPO_ROOT = Path(__file__).resolve().parents[1]


def cmd_stamp() -> int:
    manifest = stamp(REPO_ROOT)
    print(f"wrote {manifest.relative_to(REPO_ROOT).as_posix()}")
    print(ots_stamp(manifest))
    print(
        "next, in order: commit the manifest (and .ots if created), push, then run. "
        "The run guard refuses while it is uncommitted; the push is the anchor."
    )
    return 0


def cmd_verify(manifest: str | None, strict: bool) -> int:
    manifest_path = Path(manifest).resolve() if manifest else None
    verdicts = verify(REPO_ROOT, manifest_path)
    failed = False
    for v in verdicts:
        blob = "blob recoverable" if v.blob_recoverable else "BLOB UNREACHABLE"
        print(f"{v.verdict:8} {v.path}  ({blob})")
        if v.verdict == "MISSING" or not v.blob_recoverable:
            failed = True
        if strict and v.verdict != "MATCH":
            failed = True

    ots_files = sorted((REPO_ROOT / "preregistration" / "timestamps").glob("*.ots"))
    ots = shutil.which("ots")
    for path in ots_files:
        if ots is None:
            print(f"{path.name}: present, but the ots client is not installed to verify it")
            continue
        result = subprocess.run([ots, "verify", str(path)], capture_output=True, text=True, check=False)
        detail = (result.stderr or result.stdout).strip().splitlines()
        print(f"ots verify {path.name}: {detail[-1] if detail else 'no output'}")
        # The attestation is the strongest anchor the scheme has, so "could not verify it" must
        # not exit 0 the way it used to: an unverified stamp reading as a verified one is the
        # whole failure this guard exists to prevent. Note the two causes are different and the
        # wording says so, because a broken local client is not evidence of a bad timestamp.
        if result.returncode != 0:
            for line in detail:
                print(f"  {line}")
            print(
                f"  -> {path.name} is NOT verified (ots exit {result.returncode}). Either the "
                "attestation does not verify, or the local ots client failed to run; read the "
                "output above to tell which, and do not treat this stamp as an anchor until it "
                "passes."
            )
            failed = True

    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("stamp")
    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--manifest", help="specific manifest file (default: latest)")
    p_verify.add_argument("--strict", action="store_true", help="fail on any CHANGED file")
    args = parser.parse_args()
    if args.command == "stamp":
        return cmd_stamp()
    return cmd_verify(args.manifest, args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
