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
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.abstention import cells_from_records, endpoints
from harness.adapters.base import CorpusManifest
from harness.damage import CONDITIONS
from harness.plants import load_plants
from harness.tasks import discover_tasks
from scripts.assemble_condition_corpus import assemble


def selection_for(condition: str) -> list[str]:
    """Every task declaring this condition. The suite's task set is data, not a flag."""

    return [
        task.task_id
        for task in discover_tasks()
        if (spec := load_plants(task.path)) is not None and spec.plan(condition)
    ]


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
    if args.dry_run:
        command.append("--dry-run")
    print(f"[{condition}] {' '.join(command[2:])}", flush=True)
    result = subprocess.run(command, cwd=str(REPO), check=False)
    if result.returncode != 0:
        raise SystemExit(f"[{condition}] pilot exited {result.returncode}; stopping")
    return REPO / "results" / run_id


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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

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

    cells = []
    run_dirs = {}
    for condition in conditions:
        run_dirs[condition] = run_condition(args, condition)
        if not args.dry_run:
            cells.extend(load_cells(run_dirs[condition], condition))

    if args.dry_run:
        print("\n[dry-run] nothing was ingested, run or analysed")
        return 0
    if not cells:
        raise SystemExit("no admitted cells across any condition; nothing to report")

    report = endpoints(cells, arms)
    report["conditions"] = conditions
    report["n_cells"] = len(cells)
    out = REPO / "results" / f"{args.run_id}-endpoints.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"\n[abstention] {len(cells)} admitted cell(s) across {len(conditions)} condition(s)")
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
