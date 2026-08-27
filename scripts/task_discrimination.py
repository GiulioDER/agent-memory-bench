"""Which tasks in this suite can actually carry a result, and which are dead weight.

A task discriminates only if some arm can win on it and some arm can lose. A task every arm solves
contributes a zero difference to every contrast; a task no arm solves contributes another zero.
Both widen every confidence interval this benchmark publishes while adding nothing, and both are
invisible in a headline rate.

Measured on `diagnostic-009`: 8 of 24 tasks were solved by `claude_md` at 100% and 1 was failed by
every arm, leaving 15 that could move a number. That is a third of the grid carrying no signal, and
it applies retroactively to pilot-003 and pilot-004 as well.

This reports, per task, across whichever runs are present:

* the baseline rate (`bare` where a run has it, otherwise `claude_md`), which is what task
  selection should screen on
* the spread between the best and worst arm, which is the task's actual discriminating power
* a verdict: CEILING, FLOOR, or DISCRIMINATES

    python -m scripts.task_discrimination
    python -m scripts.task_discrimination --runs pilot-004-placebo diagnostic-010

Written 2026-08-27, to size the task work that preregistrations 005 and 006 both depend on.
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

DEFAULT_RUNS = (
    "pilot-003-deepseek",
    "pilot-004-placebo",
    "diagnostic-009",
    "diagnostic-010",
)

#: A task worth keeping lets the baseline succeed sometimes and fail sometimes. The band is a
#: judgement, stated here so it can be argued with rather than buried in a comparison.
BASELINE_FLOOR = 0.20
BASELINE_CEILING = 0.70


def load_run(run_id: str) -> tuple[dict[tuple[str, str], list[bool]], set[str]] | None:
    run = REPO / "results" / run_id
    records_path = run / "records.final.jsonl"
    if not records_path.is_file():
        return None
    admission_path = run / "admission.json"
    discarded: set[tuple[str, int]] = set()
    if admission_path.is_file():
        report = json.loads(admission_path.read_text(encoding="utf-8"))
        discarded = {(str(c[0]), int(c[1])) for c in report.get("discarded_cells", ())}

    by_task_arm: dict[tuple[str, str], list[bool]] = defaultdict(list)
    arms: set[str] = set()
    for line in records_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if (record["task_id"], record["seed"]) in discarded:
            continue
        by_task_arm[(record["task_id"], record["arm"])].append(bool(record["success"]))
        arms.add(record["arm"])
    return by_task_arm, arms


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="*", default=list(DEFAULT_RUNS))
    args = parser.parse_args()

    loaded = {}
    for run_id in args.runs:
        data = load_run(run_id)
        if data is None:
            print(f"  (skipping {run_id}: no records.final.jsonl)")
            continue
        loaded[run_id] = data
    if not loaded:
        raise SystemExit("no runs found")

    print(f"{'task':20s} " + " ".join(f"{r.replace('pilot-','p').replace('diagnostic-','d'):>18s}" for r in loaded))
    print(f"{'':20s} " + " ".join(f"{'base  spread verdict':>18s}" for _ in loaded))

    verdicts: dict[str, list[str]] = defaultdict(list)
    tasks = sorted({t for data, _ in loaded.values() for (t, _a) in data})

    for task in tasks:
        cells = []
        for run_id, (by_task_arm, arms) in loaded.items():
            baseline_arm = "bare" if "bare" in arms else "claude_md"
            rates = {}
            for arm in arms:
                outcomes = by_task_arm.get((task, arm))
                if outcomes:
                    rates[arm] = sum(outcomes) / len(outcomes)
            if not rates:
                cells.append(f"{'-':>18s}")
                continue
            base = rates.get(baseline_arm)
            spread = max(rates.values()) - min(rates.values())
            if base is None:
                verdict = "?"
            elif all(v >= 1.0 for v in rates.values()):
                verdict = "CEILING"
            elif all(v <= 0.0 for v in rates.values()):
                verdict = "FLOOR"
            elif spread <= 0.0:
                verdict = "FLAT"
            else:
                verdict = "ok"
            verdicts[task].append(verdict)
            # `base` is None when the baseline arm has no admitted records for this task,
            # which is what a truncated run looks like. Formatting None with %.2f raises.
            shown = "  n/a" if base is None else f"{base:5.2f}"
            cells.append(f"{shown} {spread:5.2f} {verdict:>7s}")
        print(f"{task:20s} " + " ".join(cells))

    print()
    print("=== summary across runs ===")
    dead = [t for t, v in verdicts.items() if all(x in ("CEILING", "FLOOR", "FLAT") for x in v)]
    always_ok = [t for t, v in verdicts.items() if all(x == "ok" for x in v)]
    mixed = [t for t in verdicts if t not in dead and t not in always_ok]
    print(f"  dead in EVERY run (ceiling, floor or flat): {len(dead)}/{len(verdicts)}")
    for t in dead:
        print(f"    {t}: {verdicts[t]}")
    print(f"  discriminating in every run: {len(always_ok)}/{len(verdicts)}")
    print(f"  mixed: {len(mixed)}/{len(verdicts)}")
    print()
    print(f"  A task is worth keeping if its baseline sits roughly in [{BASELINE_FLOOR}, {BASELINE_CEILING}].")
    print("  Tasks dead in every run should be retired or made harder before either new suite uses them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
