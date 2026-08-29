"""Fire every damage detector at every FACTLESS session, and require silence.

`tests/test_damage_detection.py` asks each detector to stay silent on `naive.py`: ONE committed
factless solution, written by the same person who wrote the detector. `abstention-001` showed that
is not enough. The only detector firing in 186 cells was on `claude_md`, an arm with no memory
store and `memory_call_count = 0`, whose deliverable happened to match `ts-manifest-rel`'s planted
signature. Keying a manifest of files under `release/` relative to `release/` is an entirely
natural choice that `naive.py`, which uses absolute paths, does not represent.

A real agent produces a DISTRIBUTION of factless solutions. A plant is only measurable if its
signature is outside all of them, and the only way to know is to look at real ones.

So this runs each task's detector against the finished sandbox of every session by an arm with no
memory: `bare`, which has nothing at all, and `claude_md`, which has the fixture README and no
retrieval. Any firing is a plant that cannot support a damage claim, because the outcome it
attributes to retrieval was reached without any.

    python -m scripts.validate_detectors --work-root /tmp/agent-memory-bench-work \\
        --runs abstention-001-absent abstention-001-superseded

Exit 1 if any detector fires. The named plants must then be retired or re-axed; that is not a
threshold to tune.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.damage import CONDITIONS, detect_damage
from harness.sandbox import ORACLES
from harness.tasks import discover_tasks

#: Arms with no retrieval of any kind. `claude_md` counts: a static system prompt is not a memory
#: layer, and it is the arm that exposed the defect this script exists to prevent.
FACTLESS_ARMS = ("bare", "claude_md", "placebo", "protocol")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", required=True)
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument(
        "--conditions",
        nargs="*",
        default=[c for c in CONDITIONS if c != "absent"],
        help="conditions whose detectors to test. `absent` plants nothing, so it has none.",
    )
    args = parser.parse_args()

    tasks = {task.task_id: task for task in discover_tasks()}
    work_root = Path(args.work_root)

    checked = 0
    firings: list[str] = []
    missing_runs: list[str] = []

    for run_id in args.runs:
        run_work = work_root / run_id / "work"
        if not run_work.is_dir():
            missing_runs.append(run_id)
            continue
        for task_dir in sorted(run_work.iterdir()):
            task = tasks.get(task_dir.name)
            if task is None or not (task.path / "damage.py").is_file():
                continue
            for seed_dir in sorted(task_dir.iterdir()):
                for arm_dir in sorted(seed_dir.iterdir()):
                    if arm_dir.name not in FACTLESS_ARMS or not arm_dir.is_dir():
                        continue
                    for condition in args.conditions:
                        hit, reason = detect_damage(
                            task.path, arm_dir, ORACLES / task.task_id, condition
                        )
                        checked += 1
                        if hit:
                            firings.append(
                                f"{task.task_id}/{condition}: fired on {run_id} "
                                f"{seed_dir.name}/{arm_dir.name}, which has no retrieval. {reason}"
                            )

    if missing_runs:
        print(f"  note: no sandboxes found for {missing_runs}")
    print(f"checked {checked} (task, condition, factless session) combination(s)")

    if firings:
        print(f"\nATTRIBUTION FAILURE: {len(firings)} firing(s) on sessions with no memory")
        for line in firings:
            print(f"  {line}")
        print(
            "\nEach names a plant whose damaged signature a real agent reaches WITHOUT the plant. "
            "A damage rate built on it measures ordinary failure. Retire the plant or move it to "
            "an axis the factless answer cannot reach; do not adjust a threshold."
        )
        return 1

    if not checked:
        print("nothing was checked; the work root holds no factless sandboxes for these runs")
        return 1
    print("clean: no detector fired on any session that had no memory to retrieve from")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
