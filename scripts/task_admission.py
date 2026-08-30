"""Which tasks can carry a result, on measured evidence rather than on declared plants.

    python -m scripts.task_admission
    python -m scripts.task_admission --retrieval results/retrieval/015-bm25.json
    python -m scripts.task_admission --out docs/task_admission.json

Why this exists
---------------

`docs/reviews/2026-08-30-instrument-review.md` section 2: `official-001` selected all nine tasks
the memory-free arm never fails and thirteen of the fourteen it always fails were left out. The
selection rule, `selection_for`, admits a task if it declares plants for a condition and never
asks whether anyone could fail it. Plant expressiveness and difficulty are different properties
and optimising the first discarded the second, so the suite was incapable of measuring benefit
before it started.

The screening data to fix it already exists. `resolution-001` ran all 30 tasks against `bare` at
12 seeds, and eight other runs carry per-arm outcomes. This pools them and states, per task, the
two things admission actually depends on.

The two capacities, which are not the same thing
-------------------------------------------------

A task is worth spending sessions on if it can express an OUTCOME. There are two, they are
independent, and a suite needs both:

* **benefit capacity** - the baseline sometimes fails, so a memory arm has something to win.
  A task the baseline always solves has none, whatever else is true of it.
* **damage capacity** - the baseline sometimes succeeds, so a memory arm has something to lose.
  A task the baseline never solves has none.

A task with neither contributes a zero difference to every contrast while widening every
interval this benchmark publishes. A task with only one is admissible to a suite that measures
only that one, which is why the verdict below names the capacity rather than passing a task or
failing it.

⚠️ **A `bare` rate of 0.00 is NOT a dead task.** Section 7 of the same review found the largest
memory effect in this repository on exactly those tasks: `ts-nfc-count` went 0/6 for `bare` and
8/9 for a memory arm. Those tasks have full benefit capacity and no damage capacity, and calling
them "too hard" is what kept them out of `official-001`.

The retrieval column
--------------------

With ``--retrieval``, the rank from `scripts/retrieval_probe.py` is joined in. A task whose
governing fact no retriever can find is not a task a memory product can win, however good its
difficulty band is, and the two failure modes are worth telling apart before a run rather than
after it.

This reports. It does not edit any suite list: which tasks a preregistered run admits is a
preregistration decision.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.tasks import discover_tasks

RESULTS = REPO / "results"

#: Arms that see no memory. The baseline is what a task's difficulty is measured against, and
#: `bare` is preferred: `claude_md` carries a project instruction file and is a treatment.
BASELINE_ARMS = ("bare", "claude_md")

#: Runs excluded from pooling, with the reason. Kept as an explicit dated list rather than a
#: filter expression, so removing an exclusion is a visible decision.
EXCLUDED_RUNS = {
    "pilot-003-gpt53": "incomplete: 32 of 72 cells lost to provider credit exhaustion",
    "pilot-002-repair": "a re-roll of selected cells, not a grid",
    "smoke-002": "bring-up wiring, never a result",
    "smoke-abstention-absent": "bring-up wiring, never a result",
    "smoke-sup2-superseded": "bring-up wiring, never a result",
}


def load_records() -> tuple[dict[str, dict[str, list[bool]]], list[str]]:
    """Pool every admissible run into ``task -> arm -> [success, ...]``."""

    pooled: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    used: list[str] = []
    for run in sorted(p for p in RESULTS.iterdir() if p.is_dir()):
        if run.name in EXCLUDED_RUNS:
            continue
        path = run / "records.final.jsonl"
        if not path.is_file():
            path = run / "records.jsonl"
        if not path.is_file():
            continue
        used.append(run.name)
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            success = record.get("success")
            if success is None:
                continue
            pooled[str(record["task_id"])][str(record["arm"])].append(bool(success))
    return pooled, used


def verdict(
    baseline: float | None, sessions: int, any_failure: bool, best_rate: float | None
) -> str:
    if baseline is None:
        return "UNSCREENED"
    if sessions < 6:
        return "THIN"
    if baseline >= 1.0:
        return "DAMAGE-ONLY" if any_failure else "NO-CAPACITY"
    if baseline <= 0.0:
        # A task NO arm has ever solved cannot separate two arms today, so it buys nothing in a
        # comparison run even though its benefit capacity is intact in principle. That second
        # half is why this is not folded into NO-CAPACITY: a ceiling task is finished, while a
        # floor task is waiting for a product good enough to move it.
        return "FLOOR" if best_rate is not None and best_rate <= 0.0 else "BENEFIT-ONLY"
    return "BOTH"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval", default=None, help="a retrieval_probe --out JSON file")
    parser.add_argument("--out", default=None, help="write the table to this JSON file")
    args = parser.parse_args()

    pooled, used = load_records()
    ranks: dict[str, int | None] = {}
    if args.retrieval:
        payload = json.loads(Path(args.retrieval).read_text(encoding="utf-8"))
        # The last corpus probed is the hardest one in a curve invocation, and it is the one a
        # future run would use. Taking the first would report the easiest corpus as the task's
        # retrievability, which is the flattering direction.
        for row in payload[-1]["per_task"]:
            ranks[row["task_id"]] = row["rank"]

    rows = []
    for task in sorted(discover_tasks(), key=lambda t: t.task_id):
        arms = pooled.get(task.task_id, {})
        baseline_arm = next((arm for arm in BASELINE_ARMS if arms.get(arm)), None)
        outcomes = arms.get(baseline_arm, []) if baseline_arm else []
        baseline = (sum(outcomes) / len(outcomes)) if outcomes else None
        every = [value for values in arms.values() for value in values]
        best = max((sum(v) / len(v) for v in arms.values() if v), default=None)
        rows.append(
            {
                "task_id": task.task_id,
                "kind": task.kind,
                "baseline_arm": baseline_arm,
                "baseline": round(baseline, 3) if baseline is not None else None,
                "baseline_sessions": len(outcomes),
                "sessions_all_arms": len(every),
                "failures_all_arms": sum(1 for value in every if not value),
                "best_arm_rate": round(best, 3) if best is not None else None,
                "retrieval_rank": ranks.get(task.task_id),
                "verdict": verdict(baseline, len(outcomes), any(not v for v in every), best),
            }
        )

    print(f"pooled {len(used)} runs: {', '.join(used)}")
    for run, why in sorted(EXCLUDED_RUNS.items()):
        print(f"  excluded {run}: {why}")
    print()
    header = (
        f"{'task':22s} {'kind':8s} {'base':>6} {'n':>4} {'all n':>6} {'fails':>6} "
        f"{'best':>6} {'rank':>5}  verdict"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        base = f"{row['baseline']:.2f}" if row["baseline"] is not None else "-"
        best = f"{row['best_arm_rate']:.2f}" if row["best_arm_rate"] is not None else "-"
        rank = str(row["retrieval_rank"]) if row["retrieval_rank"] else "-"
        print(
            f"{row['task_id']:22s} {row['kind']:8s} {base:>6} {row['baseline_sessions']:>4} "
            f"{row['sessions_all_arms']:>6} {row['failures_all_arms']:>6} {best:>6} "
            f"{rank:>5}  {row['verdict']}"
        )

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["verdict"]] += 1
    print("\n=== capacity ===")
    for name in (
        "BOTH", "BENEFIT-ONLY", "DAMAGE-ONLY", "FLOOR", "NO-CAPACITY", "THIN", "UNSCREENED"
    ):
        if counts[name]:
            print(f"  {name:14s} {counts[name]:>3}")
    informative = counts["BOTH"] + counts["BENEFIT-ONLY"] + counts["DAMAGE-ONLY"]
    print(
        f"\n  {informative} of {len(rows)} tasks can express an outcome today.\n"
        f"  {counts['NO-CAPACITY']} are spend: every arm already solves them.\n"
        f"  {counts['FLOOR']} are on the floor: no arm has solved them yet, so they separate "
        f"nothing until one does."
    )
    unreachable = [
        row["task_id"]
        for row in rows
        if row["retrieval_rank"] and row["retrieval_rank"] > 10 and row["verdict"] != "NO-CAPACITY"
    ]
    if unreachable:
        print(
            f"\n  outside the top 10 on the hardest probed corpus, so a memory arm has to search "
            f"deep to win at all: {', '.join(unreachable)}"
        )

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {"runs_pooled": used, "excluded": EXCLUDED_RUNS, "tasks": rows}, indent=2
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"\nwrote {out.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
