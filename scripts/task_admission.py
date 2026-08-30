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

⛔ This report CANNOT support a retirement, and that is a measured claim
------------------------------------------------------------------------

This pools the runs committed to ``results/``. `official-001` ran to completion on VPS2, 630
sessions across four conditions and five arms, and was deliberately never committed because the
instrument was miscalibrated and a ranking from it would misrepresent every arm. **Nothing in
this report sees it.**

Its NO-CAPACITY verdict has now been checked against that run twice and has been wrong twice:

* `ts-ignore-gen`, retired on this report's evidence on 2026-08-30 and reverted the same day.
  Three failures in admitted cells with no error, all under `adjacent`, one memory arm, all
  three seeds. Deterministic, attributable, and the clearest damage signal `official-001`
  produced.
* `ts-tz-utc`, flagged as a candidate by this report and checked before anyone acted. **Five**
  genuine failures spread across four arms including `bare` and `placebo`, so it is not one
  product's quirk. It is one of only a handful of tasks in the suite with any headroom at all.

Two for two is not bad luck, it is structural, and the mechanism is visible from inside this
tree. Run this report and read the arm-coverage line it prints: **no committed run contains a
single `mempalace` session**, and no committed run carries more than four arms while
`official-001` carried five. A failure that only one arm produces is invisible here by
construction, and a memory arm is exactly where damage shows up.

So, stated at the strength the evidence supports: **until `official-001` is committed or
superseded, this report cannot support a retirement at all.** It ranks candidates for somebody
with access to check them. It does not edit any suite list, and which tasks a preregistered run
admits stays a preregistration decision.
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


def load_records() -> tuple[dict[str, dict[str, list[bool]]], list[str], int]:
    """Pool every admissible run into ``task -> arm -> [success, ...]``.

    ⛔ **The unit is a failure in an ADMITTED cell with no recorded error, not ``success ==
    False``.** The first version of this counted raw outcomes, and that is wrong in the direction
    that matters: a session that crashed reads as a task the arm failed, so a task nobody can
    actually fail looks alive and stays in a suite. Across the seven pooled runs, 18 records
    carry an ``error`` and every one of them has ``success`` false.

    Two filters, and they catch different things:

    * ``admission.json`` lists the ``(task, seed)`` cells a run DISCARDED, usually because one
      arm never produced a comparable session. Those cells were excluded from the run's own
      analysis and including them here would contradict the run's published numbers.
    * ``error`` marks a session that did not complete. That is a harness outcome, not a task
      outcome.
    """

    pooled: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    used: list[str] = []
    dropped = 0
    if not RESULTS.is_dir():
        # `.dockerignore` excludes `results/`, so inside the image built by
        # `docker/Dockerfile.harness` the command this tool's own docs print raised a bare
        # `FileNotFoundError` from `iterdir`. An empty pool is a legitimate state with a
        # legitimate answer (everything UNSCREENED); a traceback is not an answer.
        return defaultdict(lambda: defaultdict(list)), [], 0
    for run in sorted(p for p in RESULTS.iterdir() if p.is_dir()):
        if run.name in EXCLUDED_RUNS:
            continue
        path = run / "records.final.jsonl"
        if not path.is_file():
            path = run / "records.jsonl"
        if not path.is_file():
            continue
        used.append(run.name)
        discarded: set[tuple[str, int]] = set()
        admission = run / "admission.json"
        if admission.is_file():
            data = json.loads(admission.read_text(encoding="utf-8"))
            discarded = {
                (str(cell[0]), int(cell[1])) for cell in data.get("discarded_cells", ())
            }
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            success = record.get("success")
            if success is None:
                continue
            task_id = str(record["task_id"])
            if record.get("error") or (task_id, int(record.get("seed", -1))) in discarded:
                dropped += 1
                continue
            pooled[task_id][str(record["arm"])].append(bool(success))
    return pooled, used, dropped


#: Sessions required before a RATE is treated as evidence rather than as an anecdote.
#:
#: ⛔ It gates a rate, and never an existence test. The 2026-08-30 audit applied it to the best
#: arm as well as the baseline, on the reasoning that both feed the same verdict, and that was
#: wrong in a way the test suite could not see: `FLOOR` asks "has ANY arm ever solved this",
#: which is a question about whether a solution exists, not about how often one occurs. Gating it
#: sent three tasks from BENEFIT-ONLY to FLOOR because their only successes came from
#: `oracle_memory`, which carries 3 sessions. One of them, `ts-log-mask`, is 3/3 for the oracle
#: against 0 for every real arm: the largest measured memory headroom in the pooled runs, filed
#: under the label this tool describes as "separates nothing". A thin arm is weak evidence about
#: a RATE and perfectly good evidence that a solution EXISTS.
MIN_SESSIONS = 6


def verdict(
    baseline: float | None, sessions: int, any_failure: bool, ever_solved: bool
) -> str:
    if baseline is None:
        return "UNSCREENED"
    if sessions < MIN_SESSIONS:
        return "THIN"
    if baseline >= 1.0:
        return "DAMAGE-ONLY" if any_failure else "NO-CAPACITY"
    if baseline <= 0.0:
        # A task NO arm has ever solved cannot separate two arms today, so it buys nothing in a
        # comparison run even though its benefit capacity is intact in principle. That second
        # half is why this is not folded into NO-CAPACITY: a ceiling task is finished, while a
        # floor task is waiting for a product good enough to move it.
        #
        # `ever_solved` is a plain existence test over every pooled session of every arm, and it
        # is symmetric with `any_failure` on the damage side. Both are existence tests; neither
        # is gated by session count, because one success is proof that a success is possible.
        #
        # Equivalence to the pre-audit test, checked exhaustively over every arms-dict of up to
        # three arms holding up to three outcomes each: `not any(every)` and the old
        # `best_rate is not None and best_rate <= 0.0` agree on every shape EXCEPT the four where
        # no arm has a single session, which the old form called BENEFIT-ONLY and this one calls
        # FLOOR. That case cannot reach here: this branch requires `baseline is not None` and
        # `sessions >= MIN_SESSIONS`, so the baseline arm contributes at least six outcomes to
        # `every`. Recorded rather than left for the next reader to rediscover, because "restores
        # the previous behaviour" is a claim and this is the check behind it.
        return "BENEFIT-ONLY" if ever_solved else "FLOOR"
    return "BOTH"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval", default=None, help="a retrieval_probe --out JSON file")
    parser.add_argument("--out", default=None, help="write the table to this JSON file")
    args = parser.parse_args()

    pooled, used, dropped = load_records()
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
        # Two different questions, published separately rather than collapsed into one number.
        #
        # `best` is the best rate among arms carrying enough sessions for a rate to be evidence,
        # which is what F-28 was actually about: `if v` (non-empty) stood here against
        # `sessions < MIN_SESSIONS` on the baseline, so a reader could not tell a rate resting on
        # 30 sessions from one resting on 1. `best_all` is the same over every arm, and
        # `ever_solved` is the existence test the FLOOR verdict turns on.
        eligible = {arm: v for arm, v in arms.items() if len(v) >= MIN_SESSIONS}
        best_arm = max(
            eligible, key=lambda arm: sum(eligible[arm]) / len(eligible[arm]), default=None
        )
        best = (
            sum(eligible[best_arm]) / len(eligible[best_arm]) if best_arm is not None else None
        )
        best_all = max((sum(v) / len(v) for v in arms.values() if v), default=None)
        ever_solved = any(every)
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
                "best_arm": best_arm,
                "best_arm_sessions": len(eligible.get(best_arm, ())),
                # Ungated, so a rate excluded by MIN_SESSIONS is visible rather than merely
                # absent. `ts-log-mask` reads best_arm_rate None, best_arm_rate_all_arms 1.0.
                "best_arm_rate_all_arms": round(best_all, 3) if best_all is not None else None,
                "ever_solved": ever_solved,
                "retrieval_rank": ranks.get(task.task_id),
                "verdict": verdict(
                    baseline, len(outcomes), any(not v for v in every), ever_solved
                ),
            }
        )

    print(f"pooled {len(used)} runs: {', '.join(used)}")
    print(
        f"  dropped {dropped} records: errored sessions and cells the run itself discarded. "
        f"A crashed session is a harness outcome, not a task outcome."
    )
    for run, why in sorted(EXCLUDED_RUNS.items()):
        print(f"  excluded {run}: {why}")
    print()
    header = (
        f"{'task':22s} {'kind':8s} {'base':>6} {'n':>4} {'all n':>6} {'fails':>6} "
        f"{'best g|all':>11} {'rank':>5}  verdict"
    )
    print(header)
    print(
        "  best g|all: left = best rate among arms with >= "
        f"{MIN_SESSIONS} sessions, which is the only rate worth reading as one. Right = best "
        "over EVERY arm. They differ where a thin arm is the only one that has solved the task, "
        "and that gap is the memory headroom, not noise: ts-log-mask reads 0.00|1.00 because "
        "oracle_memory is 3/3 against zero for every other arm."
    )
    print("-" * len(header))
    for row in rows:
        base = f"{row['baseline']:.2f}" if row["baseline"] is not None else "-"
        # BOTH rates, because the gated one alone is actively misleading: `ts-log-mask` reads
        # 0.00 there while an oracle solved it 3/3, and a reader would take 0.00 for "nothing
        # has ever worked". The left number is evidence about a rate, the right one is evidence
        # that a solution exists, and they answer different questions.
        gated = f"{row['best_arm_rate']:.2f}" if row["best_arm_rate"] is not None else "-"
        allarms = (
            f"{row['best_arm_rate_all_arms']:.2f}"
            if row["best_arm_rate_all_arms"] is not None
            else "-"
        )
        best = gated if gated == allarms else f"{gated}|{allarms}"
        rank = str(row["retrieval_rank"]) if row["retrieval_rank"] else "-"
        print(
            f"{row['task_id']:22s} {row['kind']:8s} {base:>6} {row['baseline_sessions']:>4} "
            f"{row['sessions_all_arms']:>6} {row['failures_all_arms']:>6} {best:>11} "
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
    seen = sorted({arm for arms in pooled.values() for arm in arms})
    wired = sorted(
        path.name
        for path in sorted((REPO / "adapters").iterdir())
        if path.is_dir() and (path / "adapter.py").is_file()
    )
    unseen = [arm for arm in wired if arm not in seen]
    print(f"\n  arms present in the pooled runs: {', '.join(seen)}")
    if unseen:
        print(
            f"  arms with a wired adapter and ZERO pooled sessions: {', '.join(unseen)}\n"
            f"  A failure only one of those produces is invisible to this report by construction."
        )
    # ASCII only in PRINTED text. The first version of this banner opened with a U+26D4 and
    # crashed on Windows, whose stdout is cp1252: exit 1, the banner never shown, and the
    # `--out` write below skipped silently. A warning that kills the run before it is read is
    # worse than no warning. Emoji stay fine in docstrings and comments, which are never encoded
    # to a console.
    print(
        "\n  [!!] THIS REPORT CANNOT SUPPORT A RETIREMENT. official-001 (630 sessions, five arms)"
        "\n     was deliberately never committed, so nothing above sees it. Its NO-CAPACITY"
        "\n     verdicts have been checked against that run twice and were wrong twice:"
        "\n     ts-ignore-gen (3 genuine failures) and ts-tz-utc (5, across four arms)."
        "\n     Until that run is committed or superseded, this ranks CANDIDATES for somebody"
        "\n     with access to check them, and authorises nothing."
    )
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
