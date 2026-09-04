"""Archive a condition that was interrupted mid-flight, so the run can be restarted.

`plan_conditions` REFUSES a partial condition even with `--resume`, and that refusal is correct:
resuming one would mix two runs' sessions inside a single condition and no admission report could
later separate them. But the refusal names two locations the operator then has to find by hand, a
results directory and a temp work root, and a restart that needs archaeology is a restart that does
not happen at 3am. This does that archiving deliberately and says what it moved.

    python -m scripts.archive_partial --run-id official-001

Nothing is ever deleted. A partial condition is the only surviving trace of what an aborted attempt
actually did, so both halves are MOVED into `results/archive/` with a README recording which run
they came from. A COMPLETE condition is refused outright: archiving one would silently drop a
finished result out of the run it belongs to.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness import sandbox
from scripts.abstention import condition_state

CONDITIONS = ("absent", "superseded", "contradictory", "adjacent")


def archive(run_id: str, conditions: list[str], *, dry_run: bool) -> int:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    work_root = sandbox.default_work_root()
    moved = 0

    for condition in conditions:
        run_dir = REPO / "results" / f"{run_id}-{condition}"
        work_dir = work_root / f"{run_id}-{condition}"
        state = condition_state(run_dir)

        if state == "complete":
            print(f"  {condition}: COMPLETE, refusing to archive a finished condition")
            continue
        if state == "absent" and not work_dir.is_dir():
            print(f"  {condition}: nothing to archive")
            continue

        destination = REPO / "results" / "archive" / f"{stamp}-{run_id}-{condition}"
        print(f"  {condition}: {state}")
        if dry_run:
            print(f"    would move -> {destination}")
            continue

        # exist_ok=False: `shutil.move` moves a source INTO an existing directory, so a second
        # archive landing in the same second would nest inside the first and overwrite its README.
        try:
            destination.mkdir(parents=True)
        except FileExistsError:
            print(f"    REFUSED: {destination} already exists; nothing was moved")
            continue
        records = 0
        if run_dir.is_dir():
            # `records.jsonl`, a FILE, one JSON object per session. Counted by lines rather
            # than by globbing a `records/` directory, which does not exist: that glob returned
            # 0 for every archive and the README would have understated every one of them.
            jsonl = run_dir / "records.jsonl"
            records = (
                sum(1 for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip())
                if jsonl.is_file()
                else 0
            )

        # ⚠️ The README is written BEFORE either move, not after both. Everything it says is
        # already known here, and the two moves are not atomic: a failure between them used to
        # leave an archive holding run output with nothing saying it is not a result, which is
        # the one thing this file exists to prevent.
        (destination / "README.md").write_text(
            f"# Archived partial condition: {run_id} / {condition}\n\n"
            f"Archived {stamp} by `scripts/archive_partial.py`.\n\n"
            f"This condition was interrupted before it wrote `admission.json`, so it holds "
            f"{records} record(s) for a grid that never finished. **It is not a result and must "
            f"never be reported as one**: an interrupted condition is truncated at whatever cell "
            f"the run reached, so its cells are not a sample of the grid.\n\n"
            f"It is kept rather than deleted because it is the only surviving trace of what the "
            f"aborted attempt did, which is the evidence for why it stopped.\n\n"
            f"`results/` holds that attempt's run directory and `work/` its sandboxes.\n",
            encoding="utf-8",
        )

        # Work root first: it is the half that blocks a re-run, and the results move is the half
        # that makes the condition look absent to --resume. Failing in this order leaves a state
        # --resume refuses loudly rather than one it silently offers to re-run.
        try:
            if work_dir.is_dir():
                shutil.move(str(work_dir), str(destination / "work"))
                print("    moved work root")
            if run_dir.is_dir():
                shutil.move(str(run_dir), str(destination / "results"))
                print(f"    moved results ({records} record(s))")
        except OSError as exc:
            print(
                f"    PARTIAL: {exc}. {destination} is labelled and holds whatever moved; the "
                f"rest is still in place. Finish by hand rather than re-running this script, "
                f"which would refuse the existing destination."
            )
            raise
        moved += 1

    if not dry_run and moved:
        print(f"\n{moved} condition(s) archived; re-run the suite with --resume")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="official-001")
    parser.add_argument("--conditions", default=",".join(CONDITIONS))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    print(f"archiving partial conditions for run id {args.run_id!r}")
    return archive(args.run_id, conditions, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
