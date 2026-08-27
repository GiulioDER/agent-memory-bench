"""Which tasks can carry preregistration 005's endpoints, screened on `bare` and nothing else.

Preregistration 005 requires the task screen to be fixed before any result is seen, and names
`bare` as the thing to screen on. This is that screen, executable.

## The rule comes from the estimand, not from the data

The primary endpoint is net harm, `P(arm fails AND bare succeeds) - P(arm succeeds AND bare
fails)`. Its two terms need opposite things from a task:

* the **harm** term needs `bare` to succeed, so a task `bare` never solves can only ever
  contribute zero to it;
* the **benefit** term needs `bare` to fail, so a task `bare` always solves can only ever
  contribute zero to that one.

So a task can carry the primary endpoint only if `bare` sometimes succeeds and sometimes fails.
That follows from the definition of the metric and would be the rule whatever the numbers turned
out to be, which is what makes it a screen rather than a choice.

Three strata fall out, and they are reported separately because they answer different questions:

    TWO_SIDED    0 < b < 1    both terms observable; the only stratum that can carry net harm
    DAMAGE_ONLY  b == 1       harm observable, benefit ~never; carries endpoint 2, not endpoint 1
    BENEFIT_ONLY b == 0       harm ~never observable; carries neither endpoint of this suite

"~never" rather than "never": `b` is an estimate from prior runs, so a task at 1.00 over six
observations can still fail once in a new run. The bias is asymptotic, not absolute, and pooling
the strata would push net harm positive for a reason that has nothing to do with any memory layer.

## Which runs count

Only runs that actually carried a `bare` arm, on the model preregistration 005 pins (the one
`diagnostic-009` used). A `claude_md` proxy would not do: it is handed the fixture README bundle,
so its success rate is a different quantity from the reference point damage is defined against.

    python -m scripts.select_abstention_tasks
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

#: Runs carrying a real `bare` arm on deepseek/deepseek-v4-flash, the model 005 pins. pilot-001 is
#: excluded for having no environment.json, so its model cannot be confirmed; pilot-003-gpt53 is
#: excluded for being a different model, and is printed as a cross-check rather than used.
SAME_MODEL_RUNS = ("pilot-003-deepseek", "pilot-004-placebo")
CROSS_CHECK_RUNS = ("pilot-003-gpt53",)

#: Below this many admitted `bare` observations a rate is not a screen, it is a rumour.
MIN_OBSERVATIONS = 4

TWO_SIDED, DAMAGE_ONLY, BENEFIT_ONLY, TOO_FEW = (
    "TWO_SIDED",
    "DAMAGE_ONLY",
    "BENEFIT_ONLY",
    "TOO_FEW",
)


def bare_outcomes(runs: tuple[str, ...]) -> dict[str, list[bool]]:
    """Admitted `bare` outcomes per task, pooled over runs."""

    pooled: dict[str, list[bool]] = defaultdict(list)
    for run_id in runs:
        run = REPO / "results" / run_id
        records = run / "records.final.jsonl"
        if not records.is_file():
            continue
        discarded: set[tuple[str, int]] = set()
        admission = run / "admission.json"
        if admission.is_file():
            report = json.loads(admission.read_text(encoding="utf-8"))
            discarded = {(str(c[0]), int(c[1])) for c in report.get("discarded_cells", ())}
        for line in records.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record["arm"] != "bare":
                continue
            if (record["task_id"], record["seed"]) in discarded:
                continue
            pooled[record["task_id"]].append(bool(record["success"]))
    return dict(pooled)


def stratify(outcomes: list[bool]) -> str:
    if len(outcomes) < MIN_OBSERVATIONS:
        return TOO_FEW
    rate = sum(outcomes) / len(outcomes)
    if rate <= 0.0:
        return BENEFIT_ONLY
    if rate >= 1.0:
        return DAMAGE_ONLY
    return TWO_SIDED


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the selection as JSON")
    args = parser.parse_args()

    pooled = bare_outcomes(SAME_MODEL_RUNS)
    cross = bare_outcomes(CROSS_CHECK_RUNS)
    if not pooled:
        raise SystemExit("no admitted `bare` records found; the screen has nothing to run on")

    strata: dict[str, list[str]] = defaultdict(list)
    rows = []
    for task_id in sorted(pooled):
        outcomes = pooled[task_id]
        rate = sum(outcomes) / len(outcomes)
        stratum = stratify(outcomes)
        strata[stratum].append(task_id)
        other = cross.get(task_id, [])
        rows.append(
            (task_id, rate, len(outcomes), sum(other) / len(other) if other else None, stratum)
        )

    if args.json:
        print(json.dumps({k: sorted(v) for k, v in strata.items()}, indent=2))
        return 0

    print(f"screen on `bare`, pooled over {', '.join(SAME_MODEL_RUNS)}")
    print(f"{'task':22s} {'bare':>6s} {'n':>3s} {'gpt53':>7s}  stratum")
    for task_id, rate, count, other, stratum in rows:
        other_text = "   -  " if other is None else f"{other:6.2f}"
        print(f"{task_id:22s} {rate:6.2f} {count:3d} {other_text}  {stratum}")

    print()
    for stratum in (TWO_SIDED, DAMAGE_ONLY, BENEFIT_ONLY, TOO_FEW):
        members = strata.get(stratum, [])
        if members:
            print(f"{stratum:13s} {len(members):2d}  {' '.join(members)}")

    two_sided = len(strata.get(TWO_SIDED, []))
    print()
    print(f"tasks able to carry the PRIMARY endpoint (net harm): {two_sided}")
    if two_sided < 8:
        print(
            f"  preregistration 005 reports a condition with fewer than 8 admitted tasks as "
            f"UNDERPOWERED rather than as a result. At {two_sided}, the primary endpoint cannot "
            f"be delivered at adequate power on the current task suite."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
