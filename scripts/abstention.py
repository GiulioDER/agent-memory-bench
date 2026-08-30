"""Run preregistration 005's abstention suite: one grid per corpus condition, then the endpoints.

Each condition is a SEPARATE run with its own corpus, its own memory namespace and its own
artifacts, because the thing that differs between them is the feed every arm ingests. Pooling them
into one run directory would make the per-condition discards 005 requires impossible to report.

    python -m scripts.abstention --run-id abstention-001 --conditions absent,superseded

Per condition it does four things:

1. **Assembles** the condition corpus with `scripts/assemble_condition_corpus.py`, which composes
   the base corpus with that condition's plants and withholdings and writes a manifest.
2. **Ingests** it into a namespace of its own, `<namespace>-<condition>`. This is the step that
   makes conditions independent: a shared tenant would leave the previous condition's memos in the
   store, and `absent` would silently be `fact-present`.
3. **Runs the grid** by invoking `scripts/pilot.py` with `--corpus-root` and `--condition`, so the
   measured path is the same instrument every other run uses rather than a parallel one.
4. **Classifies** each cell through its task's damage detector, inside the runner, while the
   sandbox still exists. That happens in pilot.py; there is nowhere else it can happen.

Afterwards it reads every condition's admitted records and computes the four endpoints via
`harness/abstention.py`.

## Which arms run, and why `fs_grep` is not one of them yet

Preregistration 005 freezes three: `bare`, `claude_md`, `recall`. `fs_grep` exists and would
strengthen the comparison, being a memory arm with no vendor behind it, but adding an arm to a
preregistered grid changes the record rather than the run. It goes in the NEXT record, alongside
whatever else that one adds; decided 2026-08-28.

## `bare` is mandatory and this refuses without it

Damage is "the arm failed a cell `bare` solved". Without that arm the primary and secondary
endpoints are undefined, and 005 says so in terms. `diagnostic-003` onward dropped `bare` and
that is exactly how the suite lost the ability to express harm.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.abstention import cells_from_records, endpoints
from harness.adapters.base import CorpusManifest
from harness.costs import add_pricing_arguments, pricing_from_args
from harness.damage import CONDITIONS
from harness.plants import load_plants
from harness.tasks import discover_tasks
from scripts.assemble_condition_corpus import assemble

# Tasks retired from the harm suite on 2026-08-30 because **no arm has ever failed them**, across
# every run in this repository plus official-001. A task nobody fails can record neither damage
# (failing what `bare` solved) nor benefit (solving what `bare` failed). It is spend, not evidence.
#
# The value is the number of sessions behind each, which is what makes this a measurement rather
# than an impression. Retired by list rather than by deleting their plants, so the decision is
# reversible, the authoring work is preserved, and a future harder model can re-admit them.
#
# See docs/reviews/2026-08-30-instrument-review.md. official-001 spent 82.2% of its sessions on
# cells where every arm produced the same outcome; this is the first cut against that.
RETIRED_TASKS = {
    "ts-glob-hidden": "0 failures in 113 sessions, every arm, every run",
    "ts-bool-env": "0 failures in 62 sessions",
    "ts-csv-quote": "0 failures in 54 sessions",
    "ts-append-only": "1 failure in 117 sessions, which cannot separate two arms either",
}


def selection_for(condition: str, *, announce: bool = True) -> list[str]:
    """Every task declaring this condition, minus the ones retired for carrying no information.

    ⛔ The exclusion is ANNOUNCED rather than silent. The last time this suite dropped something
    quietly it was an entire product arm missing from MEMORY_ARMS, which cost official-001 its
    search-rate reporting and was invisible in the artifact. A grid that shrinks without saying so
    is the same failure with a different subject.
    """

    declared = [
        task.task_id
        for task in discover_tasks()
        if (spec := load_plants(task.path)) is not None and spec.plan(condition)
    ]
    kept = [t for t in declared if t not in RETIRED_TASKS]
    dropped = [t for t in declared if t in RETIRED_TASKS]
    if dropped and announce:
        for task in dropped:
            print(f"[retired] {condition}: {task} excluded ({RETIRED_TASKS[task]})")
    return kept


def ingest_recall(corpus_root: Path, namespace: str, *, dry_run: bool) -> dict | None:
    """Load this condition's feed into its own tenant, so conditions cannot contaminate each other.

    Imported lazily: the adapter reaches for a database and a model, and a dry run must not.
    """

    if dry_run:
        print(f"[dry-run] would ingest {corpus_root} into tenant {namespace}")
        return None
    from adapters.recall.adapter import RecallAdapter

    corpus = CorpusManifest.load(corpus_root)
    corpus.verify()
    # `ingest` reads only `staging_root`; the prompt file and instruction belong to a SESSION and
    # are inert here. It still gets a real file rather than a convenient one: passing the corpus
    # manifest as a prompt worked only because nothing validated it, and that is the kind of thing
    # that holds until someone adds a check.
    staging = REPO / "results" / ".ingest-staging"
    adapter = RecallAdapter(staging, REPO / "adapters" / "_shared" / "memory_protocol.md")
    report = adapter.ingest(corpus, namespace)
    print(f"[ingest] recall  {namespace}: {report.items_stored} item(s)")
    return report.to_dict()


def preflight_recall(namespace: str, *, dry_run: bool) -> None:
    """Refuse the run unless the recall arm's MCP server actually starts and offers its tools.

    ⛔ This exists because a dead stdio server is invisible in a session record. The model gets no
    memory tools, answers from the sandbox, and the cell records `memory_call_count = 0`, which is
    exactly what an agent that chose not to search records. `error` stays null.

    Twenty-two sessions of `abstention-002` were spent that way on 2026-08-29 across two distinct
    causes, a wrong interpreter and a missing `mcp` extra, and both were found by noticing a search
    rate of zero afterwards. Six seconds of handshake before the first session is the cheap version
    of that discovery.
    """

    if dry_run:
        print(f"[dry-run] would preflight the recall MCP server for {namespace}")
        return
    from adapters.recall.adapter import RecallAdapter
    from harness.mcp_probe import probe

    staging = REPO / "results" / ".ingest-staging"
    adapter = RecallAdapter(staging, REPO / "adapters" / "_shared" / "memory_protocol.md")
    with tempfile.TemporaryDirectory() as temp:
        spec = adapter.build(Path(temp) / "preflight", namespace)
        required = [
            name.removeprefix(str(adapter.config["tool_prefix"]))
            for name in spec.extra_allowed_tools
        ]
        tools = probe(spec.mcp_config, str(adapter.config["server_name"]), required)
    print(f"[preflight] recall MCP server up for {namespace}: {len(tools)} tool(s), {required} present")



def condition_state(run_dir: Path) -> str:
    """`complete`, `partial`, or `absent`, for one condition's run directory.

    A condition is COMPLETE only when it wrote `admission.json`, because that file is the last
    thing a finished condition produces: it exists if and only if every cell was run and judged.
    Records alone are not enough, and that distinction is the whole point of this function.
    `abstention-002` was killed mid-condition and left 86 of 90 records with no admission file, so
    a resume keyed on "has records" would have treated a truncated condition as done and published
    it.
    """

    if not run_dir.is_dir():
        return "absent"
    if (run_dir / "admission.json").is_file():
        return "complete"
    return "partial" if any(run_dir.iterdir()) else "absent"


def plan_conditions(run_id: str, conditions: list[str], *, resume: bool) -> list[str]:
    """Which conditions this invocation should actually run.

    ⛔ A PARTIAL condition is refused rather than resumed or overwritten, and it is refused even
    with `--resume`. Re-running it would hit the results guard; silently continuing it would mix
    two runs' sessions inside one condition, which no admission report could later separate. The
    operator archives it deliberately, exactly as `abstention-002`'s partials were archived with a
    README saying what they are.
    """

    todo, done, blocked = [], [], []
    for condition in conditions:
        state = condition_state(REPO / "results" / f"{run_id}-{condition}")
        if state == "complete" and resume:
            done.append(condition)
        elif state == "partial":
            blocked.append(condition)
        else:
            todo.append(condition)
    if blocked:
        raise SystemExit(
            f"{blocked} already hold a PARTIAL run: records were written but no admission.json, "
            f"so the condition was interrupted mid-flight. Archive each directory (and its work "
            f"root under the temp work area) before re-running it. Resuming a partial condition "
            f"would mix two runs' sessions inside one condition and no later report could "
            f"separate them."
        )
    if done:
        print(f"[resume] already complete, skipping: {done}")
    if not todo:
        raise SystemExit("[resume] every requested condition is already complete; nothing to do")
    return todo


def run_condition(args, condition: str) -> Path:
    """Assemble, ingest and run one condition. Returns its run directory."""

    selection = selection_for(condition)
    if args.tasks:
        wanted = [item.strip() for item in args.tasks.split(",") if item.strip()]
        missing = [task_id for task_id in wanted if task_id not in selection]
        if missing:
            raise SystemExit(
                f"{missing} do not declare the {condition!r} condition, so they cannot be run "
                f"under it. A silent subset is a different suite."
            )
        selection = [task_id for task_id in selection if task_id in set(wanted)]
    if not selection:
        raise SystemExit(
            f"no task declares the {condition!r} condition. Declare it in a task's plants.json "
            f"before running it, or the condition is a name with no corpus behind it."
        )

    corpus_root = REPO / "corpus" / "conditions" / condition / f"seed-{args.seed}"
    provenance = assemble(condition, args.seed, selection, corpus_root)
    print(
        f"[{condition}] {len(selection)} task(s), "
        f"{provenance['sessions_total']} session file(s) in the feed"
    )

    namespace = f"{args.namespace}-{condition}"
    if "recall" in args.arms.split(","):
        ingest_recall(corpus_root, namespace, dry_run=args.dry_run)
        # After ingest, because the server is checked against the corpus it will serve.
        preflight_recall(namespace, dry_run=args.dry_run)

    run_id = f"{args.run_id}-{condition}"
    command = [
        sys.executable, "-m", "scripts.pilot",
        "--run-id", run_id,
        "--arms", args.arms,
        "--tasks", ",".join(selection),
        "--seeds", str(args.seeds),
        "--model", args.model,
        "--namespace", namespace,
        "--corpus-root", str(corpus_root),
        "--condition", condition,
        "--memory-instruction", args.memory_instruction,
    ]
    # Forwarded rather than defaulted, so every condition of a suite is priced identically and
    # the basis is the one the operator chose.
    for flag, value in (
        ("--price-in", args.price_in),
        ("--price-out", args.price_out),
        ("--price-as-of", args.price_as_of),
        ("--price-cache-read", args.price_cache_read),
        ("--price-cache-creation", args.price_cache_creation),
    ):
        if value is not None:
            command += [flag, str(value)]
    if args.dry_run:
        command.append("--dry-run")
    print(f"[{condition}] {' '.join(command[2:])}", flush=True)
    result = subprocess.run(command, cwd=str(REPO), check=False)
    if result.returncode != 0:
        raise SystemExit(f"[{condition}] pilot exited {result.returncode}; stopping")
    return REPO / "results" / run_id


#: Below this, a memory arm's endpoints are not interpretable. Taken from preregistration 002's
#: eligibility rule rather than chosen here, so the benchmark uses one number for one idea.
SEARCH_RATE_FLOOR = 0.50

#: Arms whose treatment is a memory surface, so a search rate is defined for them.
# Arms whose treatment IS retrieval, and which therefore need a search rate beside every
# endpoint. Preregistration 014 requires one per memory arm, with 0.50 as the floor below which
# the endpoints are not interpretable.
#
# ⛔ `mempalace` was missing from this set for the whole of `official-001`, so the run published
# no search rate for it and never applied the floor to it. It was not a small omission: measured
# afterwards on the `absent` condition, recall searched in 28 of 33 sessions (0.848) and mempalace
# in 18 of 33 (0.545), which is barely above the floor and materially different from the arm it is
# being compared against. The endpoints were computed as though that were unknown, because it was.
#
# The failure mode is what makes it worth a comment: adding a product arm to the run required no
# change here, so the arm ran, produced records, and was silently exempted from the one check that
# decides whether its numbers mean anything. `_classify_arms` below now refuses an arm that is in
# neither set, so the next product cannot repeat it.
MEMORY_ARMS = frozenset({"recall", "mempalace", "fs_grep"})

# Arms with no retrieval surface. A search rate for these is meaningless, not missing.
NON_MEMORY_ARMS = frozenset({"bare", "placebo", "claude_md", "protocol"})


def _classify_arms(arms: Iterable[str]) -> None:
    """Refuse a run whose arms are not all classified as memory or non-memory.

    Silence is the whole hazard here. An unclassified arm does not error, it simply never appears
    in `search_rates`, and a reader sees a table with one fewer row rather than a warning.
    """

    unknown = sorted(set(arms) - MEMORY_ARMS - NON_MEMORY_ARMS)
    if unknown:
        raise SystemExit(
            f"arm(s) {unknown} are classified neither as memory arms nor as memoryless controls. "
            f"Add them to MEMORY_ARMS or NON_MEMORY_ARMS in scripts/abstention.py. An "
            f"unclassified arm silently gets no search rate and no interpretability floor, which "
            f"is how official-001 published endpoints for an arm whose search rate nobody knew."
        )


def search_rate_for(run_dir: Path) -> dict[str, float]:
    """Fraction of each memory arm's admitted cells that called its memory at least once.

    Reported beside every endpoint because it decides whether they mean anything. pilot-003 and
    pilot-004 measured 0.833 and 0.857 overall with the same instruction; a run far below that is
    measuring an arm that did not use its treatment.
    """

    records_path = run_dir / "records.final.jsonl"
    if not records_path.is_file():
        return {}
    calls: dict[str, list[bool]] = {}
    for line in records_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        arm = str(record["arm"])
        if arm not in MEMORY_ARMS:
            continue
        calls.setdefault(arm, []).append(int(record.get("memory_call_count") or 0) > 0)
    # A memory arm that searched in NONE of its cells still gets a rate of 0.0, because that is
    # the number the reader needs. Dropping it would hide exactly the case this exists to catch.
    return {arm: sum(seen) / len(seen) for arm, seen in calls.items() if seen}


def load_cells(run_dir: Path, condition: str):
    """Admitted records only. A discarded cell has no treatment and cannot carry an outcome."""

    records_path = run_dir / "records.final.jsonl"
    if not records_path.is_file():
        return []
    discarded = set()
    admission = run_dir / "admission.json"
    if admission.is_file():
        report = json.loads(admission.read_text(encoding="utf-8"))
        discarded = {(str(c[0]), int(c[1])) for c in report.get("discarded_cells", ())}
    admitted = [
        record
        for line in records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for record in [json.loads(line)]
        if (record["task_id"], record["seed"]) not in discarded
    ]
    return cells_from_records(admitted, condition)



def fill_missing_search_rates(
    search_rates: dict[str, float | None],
    arms: Sequence[str],
    conditions: Sequence[str],
) -> dict[str, float | None]:
    """Give every requested memory arm a rate in every condition, `None` where it has no records.

    `search_rate_for` keys its result off the arms it OBSERVES, so an arm that produced no records
    is simply absent. The floor is then applied to a dict the arm is not in, `any(...)` over the
    survivors is False, and the gate passes BECAUSE the evidence is missing. `_classify_arms`
    validates arm NAMES and cannot catch it.
    """

    filled = dict(search_rates)
    for arm in arms:
        if arm not in MEMORY_ARMS:
            continue
        for condition in conditions:
            filled.setdefault(f"{arm}[{condition}]", None)
    return filled


def interpretability(search_rates: dict[str, float | None]) -> dict[str, bool]:
    """Which arms' endpoints mean anything, at `SEARCH_RATE_FLOOR`.

    `None` means the arm produced no records, which is LESS interpretable than a low rate, not
    more. This read `rate is None or rate >= FLOOR`, a branch that could never fire because
    `search_rate_for` returns `dict[str, float]`, and that had the polarity backwards if it ever
    did.
    """

    return {
        arm: rate is not None and rate >= SEARCH_RATE_FLOOR
        for arm, rate in search_rates.items()
    }


def below_the_floor(search_rates: dict[str, float | None]) -> bool:
    """True when any arm is under the floor OR has no rate at all."""

    return any(rate is None or rate < SEARCH_RATE_FLOOR for rate in search_rates.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="abstention-001")
    parser.add_argument("--conditions", default="absent,superseded")
    parser.add_argument("--arms", default="bare,claude_md,recall")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=1, help="corpus assembly seed")
    parser.add_argument("--model", default="deepseek/deepseek-v4-flash")
    parser.add_argument(
        "--tasks",
        default="",
        help="comma-separated subset of the tasks declaring the condition. For smoke tests only: "
        "a preregistered run's task set comes from the records, not from this flag. Note the "
        "CORPUS is unaffected, since non-selected tasks keep their sessions by design, so a "
        "subset shrinks the grid without making the retrieval problem easier.",
    )
    parser.add_argument("--namespace", default="bench-abstention")
    parser.add_argument(
        "--memory-instruction",
        default="skill",
        help="the instruction each memory arm carries. Defaults to `skill`, meaning EACH ARM "
        "SHIPS ITS OWN, because preregistration 006 requires every arm to be wired through its "
        "own official integration and forbids prescribing the route. `protocol` equalises the "
        "text across arms, which is a useful ablation and is NOT the product comparison: it "
        "measures a common denominator none of the products actually ships.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip conditions that already wrote admission.json. A PARTIAL condition is "
        "refused either way: it must be archived by hand, because resuming one would mix "
        "two runs' sessions inside a single condition.",
    )
    parser.add_argument(
        "--analyse-only",
        action="store_true",
        help="recompute the endpoints from conditions that already finished; run nothing",
    )
    parser.add_argument("--dry-run", action="store_true")
    add_pricing_arguments(parser)
    args = parser.parse_args()

    # Validated HERE, before the first ingest, even though this script prices nothing itself and
    # only forwards the rates to pilot. Letting pilot refuse would be correct and far too late:
    # each condition ingests its own corpus into its own tenant first, so the run would spend the
    # embedding cost of every condition before dying on a missing flag.
    if not args.dry_run:
        pricing_from_args(args, model=args.model)

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    unknown = [c for c in conditions if c not in CONDITIONS]
    if unknown:
        raise SystemExit(f"unknown condition(s) {unknown}; choose from {CONDITIONS}")

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    if "bare" not in arms:
        raise SystemExit(
            "the `bare` arm is mandatory for this suite. Damage is defined as failing a cell "
            "bare solved, so without it the primary and secondary endpoints are undefined rather "
            "than merely weaker. Preregistration 005 says so in terms."
        )

    _classify_arms(arms)

    cells = []
    requested = list(conditions)
    run_dirs = {}
    search_rates: dict[str, float | None] = {}

    # `--analyse-only` re-derives the endpoints from conditions that already finished, running
    # nothing and spending nothing. It exists because the endpoints of `official-001` had to be
    # recomputed after a bug in arm classification, and without it the only way to fix a analysis
    # defect was to re-run 630 sessions, which would have replaced the very data being corrected.
    if not args.analyse_only:
        for condition in plan_conditions(args.run_id, requested, resume=args.resume):
            run_dirs[condition] = run_condition(args, condition)

    if not args.dry_run:
        for condition in requested:
            run_dir = REPO / "results" / f"{args.run_id}-{condition}"
            if condition_state(run_dir) != "complete":
                print(f"[analyse] skipping {condition}: not complete")
                continue
            run_dirs[condition] = run_dir
            cells.extend(load_cells(run_dir, condition))
            for arm, rate in search_rate_for(run_dir).items():
                search_rates[f"{arm}[{condition}]"] = rate
        conditions = sorted(run_dirs)

    if args.dry_run:
        print("\n[dry-run] nothing was ingested, run or analysed")
        return 0
    if not cells:
        raise SystemExit("no admitted cells across any condition; nothing to report")

    # An arm with NO records never reaches `search_rates`, so without this the floor cannot see it.
    search_rates = fill_missing_search_rates(search_rates, arms, conditions)

    report = endpoints(cells, arms)
    report["conditions"] = conditions
    report["n_cells"] = len(cells)
    report["search_rates"] = search_rates
    # A memory arm that never searched cannot be damaged by what it would have retrieved, so a
    # low rate does not weaken these endpoints, it voids them. Preregistration 002 already uses
    # 0.50 as a floor for model eligibility; the same number is applied here rather than a new
    # one invented for the occasion.
    report["interpretable"] = interpretability(search_rates)
    out = REPO / "results" / f"{args.run_id}-endpoints.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"\n[abstention] {len(cells)} admitted cell(s) across {len(conditions)} condition(s)")
    for label, rate in sorted(search_rates.items()):
        if rate is None:
            print(
                f"  search rate {label:26s}   none  <-- NO RECORDS, ENDPOINTS NOT INTERPRETABLE"
            )
            continue
        flag = "" if rate >= SEARCH_RATE_FLOOR else "  <-- BELOW FLOOR, ENDPOINTS NOT INTERPRETABLE"
        print(f"  search rate {label:26s} {rate:.3f}{flag}")
    if below_the_floor(search_rates):
        print(
            f"\n  A memory arm searched in fewer than {SEARCH_RATE_FLOOR:.0%} of its cells. It "
            f"cannot be damaged by evidence it never retrieved, so every figure below describes "
            f"an arm that did not use its treatment. pilot-003 and pilot-004 measured 0.833 and "
            f"0.857 with the same instruction, so a rate far below that is a finding in itself."
        )
    for arm, block in report["arms"].items():
        print(f"\n  {arm}")
        for stratum, stats in block["1_net_harm_by_stratum"].items():
            flag = " UNDERPOWERED" if stats["underpowered"] else ""
            note = "" if stats["interpretable"] else "  (not a net-harm stratum)"
            print(
                f"    net harm [{stratum}] {stats['net_harm']:+.3f} "
                f"over {stats['n_tasks']} task(s){flag}{note}"
            )
        for condition, stats in block["2_damage_rate_by_condition"].items():
            print(f"    damage rate [{condition}] {stats['damage_rate']:.3f}")
        for condition, stats in block["3_abstention_rate"].items():
            print(f"    abstention [{condition}] {stats['rate']:.3f} (lower bound)")
    print(f"\n  endpoints: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
