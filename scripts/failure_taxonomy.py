"""Where a memory arm's failures actually come from, split by class rather than counted.

EXPLORATORY. Preregistration 003 names its own primary metrics and this is not among them; this
splits an already-measured arm four ways so that the next thing built is chosen by which class
dominates, rather than by which is easiest to improve.

The classes, in the order a session passes through them:

* **did not search** the memory layer was available and never called. A behavioural result about
  discoverability, not a wiring failure, which is why the admission gate counts these rather than
  discarding them.
* **searched, governing memo not reached** it searched and the task's governing precursor never
  appeared in what came back.
* **reached it, still failed** the governing precursor was in the retrieved context and the task
  was still not solved.
* **reached it, solved**

Two limits, stated because they decide what the numbers can carry:

1. "Reached" means the governing precursor appeared in `retrieved_contexts` or in an MCP tool
   result. It does not prove the model READ it, nor that it was ranked where a reader would look.
2. This cannot separate "searched and found nothing" from "searched and found the wrong thing".
   Both land in one class. That cut needs the prefetch arm, which records what retrieval actually
   returned for the exact task prompt, independent of what the agent chose to ask.

Run on the admitted cells of any run carrying a searching arm:

    python -m scripts.failure_taxonomy --run-id pilot-004-placebo --arm recall

Written 2026-08-25.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

CLASSES = (
    "did not search",
    "searched, governing memo not reached",
    "reached it, still failed",
    "reached it, solved",
)


def reached_governing_memo(record: dict) -> bool:
    """Did the task's own precursor session come back from the memory layer?"""

    tag = f"sessions__{record['task_id']}__"
    if any(tag in context for context in record.get("retrieved_contexts") or ()):
        return True
    return any(
        tag in str(call.get("output", ""))
        for call in record.get("tool_calls") or ()
        if str(call.get("name", "")).startswith("mcp__")
    )


def classify(record: dict) -> str:
    if record.get("memory_call_count", 0) <= 0:
        return "did not search"
    if not reached_governing_memo(record):
        return "searched, governing memo not reached"
    return "reached it, solved" if record["success"] else "reached it, still failed"


def taxonomy(records: list[dict], discarded: set[tuple[str, int]], arm: str) -> dict:
    admitted = [
        record
        for record in records
        if record["arm"] == arm and (record["task_id"], record["seed"]) not in discarded
    ]
    buckets: dict[str, list[dict]] = {name: [] for name in CLASSES}
    for record in admitted:
        buckets[classify(record)].append(record)
    failures = [record for record in admitted if not record["success"]]
    return {
        "arm": arm,
        "admitted_sessions": len(admitted),
        "successes": len(admitted) - len(failures),
        "failures": len(failures),
        "classes": {
            name: {
                "n": len(group),
                "share_of_all": round(len(group) / len(admitted), 4) if admitted else None,
                "solved": sum(1 for record in group if record["success"]),
                "failed": sum(1 for record in group if not record["success"]),
                "share_of_failures": (
                    round(sum(1 for r in group if not r["success"]) / len(failures), 4)
                    if failures
                    else None
                ),
            }
            for name, group in buckets.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arm", default="recall")
    parser.add_argument("--json", action="store_true", help="emit the machine readable form")
    args = parser.parse_args()

    run_dir = REPO / "results" / args.run_id
    records = [
        json.loads(line)
        for line in (run_dir / "records.final.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    admission_path = run_dir / "admission.json"
    discarded: set[tuple[str, int]] = set()
    if admission_path.is_file():
        report = json.loads(admission_path.read_text(encoding="utf-8"))
        discarded = {(str(cell[0]), int(cell[1])) for cell in report.get("discarded_cells", ())}
    else:
        raise SystemExit(f"no admission report at {admission_path}; refusing to score every cell")

    result = taxonomy(records, discarded, args.arm)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(
        f"{args.run_id} / arm {result['arm']}: {result['successes']}/{result['admitted_sessions']} "
        f"solved, {result['failures']} failures"
    )
    print(f"\n{'class':40s} {'n':>4s} {'of all':>8s} {'solved':>8s} {'of failures':>12s}")
    for name in CLASSES:
        row = result["classes"][name]
        share = "n/a" if row["share_of_all"] is None else f"{row['share_of_all']:.1%}"
        of_fail = "n/a" if row["share_of_failures"] is None else f"{row['share_of_failures']:.0%}"
        print(f"{name:40s} {row['n']:4d} {share:>8s} {row['solved']:>4d}/{row['n']:<3d} {of_fail:>12s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
