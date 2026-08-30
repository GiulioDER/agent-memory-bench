"""Build one condition's corpus for the abstention suite, from the base corpus plus plants.

Output is an ordinary corpus root, so `CorpusManifest.build` and every adapter work against it
with no changes:

    corpus/conditions/<condition>/seed-<n>/
        sessions/<task_id>/*.jsonl
        distractors/*.jsonl
        manifest.json
        condition.json        provenance: what was swapped, for what, under which seed

## Only the SELECTED tasks are altered, and every other session stays

A condition corpus is not "the selected tasks' sessions". Non-selected tasks keep their real
sessions and the distractors are copied whole, so the feed stays the same size and the retrieval
problem stays the same difficulty. Shrinking the corpus to the 12 tasks under test would quietly
benchmark an easier retrieval problem than every run published so far, and the resulting damage
rate would not be comparable with anything. Containment is what makes this safe: the corpus audit
already asserts that no task's governing fact appears in any other task's sessions.

## Timestamps

`ts` is recording metadata that the pipeline already maps onto the project timeline, as the corpus
README discloses. `contradictory` re-maps it once more, permuting which of the two disagreeing
memos is dated earlier per seed, so recording order cannot decide the tie. Content is never
touched.

    python -m scripts.assemble_condition_corpus --condition superseded --seed 1
    python -m scripts.assemble_condition_corpus --condition absent --seed 1 --tasks ts-base36-id
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.adapters.base import CorpusManifest
from harness.damage import CORPUS_CONDITIONS, PRESENT
from harness.plants import (
    PlantSpecError,
    assign_contradiction_dates,
    load_plants,
    present_plan,
    sources_for,
)
from harness.tasks import discover_tasks

BASE_CORPUS = REPO / "corpus"
CONDITIONS_ROOT = BASE_CORPUS / "conditions"

#: Matches `scripts/record_precursor.py`, so a re-stamped session is indistinguishable in shape
#: from one the recorder wrote.
TURN_SECONDS = 40
DAY_START_HOUR = 9


def restamp(lines: list[dict], session_date: str) -> list[dict]:
    """Re-map every `ts` onto a new session date, 40s per turn from 09:00 UTC.

    Content is untouched; only recording metadata moves.
    """

    base = datetime.strptime(session_date, "%Y-%m-%d").replace(
        hour=DAY_START_HOUR, tzinfo=UTC
    )
    stamped = []
    for index, line in enumerate(lines):
        moved = dict(line)
        moved["ts"] = (base + timedelta(seconds=TURN_SECONDS * index)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        stamped.append(moved)
    return stamped


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    """Write a re-stamped session with LF endings, matching every other file in the feed.

    ``newline="\\n"`` is load-bearing on Windows, where the default translates to CRLF. A
    re-stamped memo would then be the only CRLF file among 125 LF ones, differing in bytes for a
    reason that has nothing to do with its condition: it could chunk differently from the sessions
    it competes with, which is the salience confound preregistration 005 names, and the corpus
    would hash differently depending on whether it was assembled here or on the run host.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines)
    path.write_text(body, encoding="utf-8", newline="\n")


from scripts.pilot import EXCLUDED_PREFIXES, SELECTABLE_PREFIXES


def default_selection(condition: str) -> list[str]:
    """Every task this condition can be built for, before any retirement list is applied.

    ⚠️ The rule differs for `present` and that is the whole point of the condition.

    An adversarial condition is a claim about a planted memo, so a task qualifies by DECLARING
    one. Section 2 of `docs/reviews/2026-08-30-instrument-review.md` traced official-001's central
    defect to that rule: plant expressiveness and difficulty are different properties, and
    admitting on the first silently discarded the second, leaving a suite that could not measure
    benefit at all.

    `present` needs no plant, so applying the same rule would inherit the same bias and hand the
    one condition that CAN measure benefit only the 15 tasks somebody has authored plants for.
    Measured 2026-08-30: the declaring rule gives 15, this one gives 29, and the 14 it adds
    include `ts-nfc-count`, `ts-round-money` and `ts-quote-shell`, which are precisely the tasks
    section 7 of that review named as where a memory arm converts impossible into solved.

    ⛔ Note what selection does and does not do here. For `present` the corpus is the identity
    transform, so selecting a task changes NO bytes; it changes which tasks `condition.json`
    records as under test, and therefore which cells the run grid covers. Getting it wrong
    produces a corpus that looks right and a run that measures a third of what it should.
    """

    return [t for t in _declared_for(condition) if t.startswith(SELECTABLE_PREFIXES)]


def _declared_for(condition: str) -> list[str]:
    """Tasks the condition can be built for, BEFORE the class filter. See `excluded_by_class`."""

    if condition == PRESENT:
        return [
            task.task_id
            for task in discover_tasks()
            if task.fact_terms and any((BASE_CORPUS / "sessions" / task.task_id).glob("*.jsonl"))
        ]
    return [
        task.task_id
        for task in discover_tasks()
        if (spec := load_plants(task.path)) is not None and spec.plan(condition)
    ]


def excluded_by_class(condition: str) -> list[tuple[str, str]]:
    """`(task, reason)` for every task this condition could cover but whose CLASS the grid refuses.

    `scripts/pilot.py` accepts only `SELECTABLE_PREFIXES` and records why each other class is out
    in `EXCLUDED_PREFIXES`. `default_selection` applies that filter so the assembler and the runner
    cannot disagree about which tasks are under test; this exposes what it removed so the drop can
    be announced rather than discovered.

    ⚠️ It never fired on the four adversarial conditions, because a task qualifies there by
    declaring plants and no `xs-` task does. `present` selects on having a recorded governing
    session instead, so it picks up all three and a run died at argument validation with "unknown
    task(s)". The pilot's refusal was correct; the selector was the thing that was wrong.
    """

    out = []
    for task in _declared_for(condition):
        if task.startswith(SELECTABLE_PREFIXES):
            continue
        prefix = next((p for p in EXCLUDED_PREFIXES if task.startswith(p)), None)
        out.append((task, EXCLUDED_PREFIXES.get(prefix, "not a class the grid runs")))
    return out


def assemble(condition: str, seed: int, selection: list[str], out_root: Path) -> dict:
    if condition not in CORPUS_CONDITIONS:
        raise SystemExit(f"unknown condition {condition!r}; expected one of {CORPUS_CONDITIONS}")

    tasks = {task.task_id: task for task in discover_tasks()}
    unknown = [task_id for task_id in selection if task_id not in tasks]
    if unknown:
        raise SystemExit(f"unknown task(s) in selection: {unknown}")

    # Defence in depth, at the layer that actually DELETES. The containment check lives in
    # `main()` and covers `--out` only, so the other four callers reach this `rmtree` with a
    # constructed path and no check at all. Not exploitable today (the condition is validated
    # above and every caller builds its own path), which is exactly the state to add a guard in
    # rather than after.
    #
    # The rule is about WHAT is being removed, not where it sits: a location whitelist would
    # have refused every test that assembles into a tmp directory, which is a legitimate caller.
    # This function writes exactly the entries below, so a target holding anything else is not a
    # condition corpus this code built and must not be deleted wholesale.
    WRITES = {"sessions", "distractors", "condition.json", "manifest.json"}
    if out_root.exists():
        # `.DS_Store`, `Thumbs.db` and `desktop.ini` are written by a file browser, not by a
        # person, and refusing a legitimate re-assemble because one appeared would make this
        # guard a nuisance that gets deleted rather than a guard.
        IGNORED = {".DS_Store", "Thumbs.db", "desktop.ini"}
        foreign = sorted(
            p.name
            for p in out_root.iterdir()
            if p.name not in WRITES and p.name not in IGNORED
        )
        if foreign:
            raise SystemExit(
                f"refusing to delete {out_root.resolve()}: it holds {foreign}, which this "
                f"function does not write, so it is not a condition corpus built by this code. "
                f"Remove it deliberately if that is what you meant."
            )
        shutil.rmtree(out_root)
    (out_root / "sessions").mkdir(parents=True)
    (out_root / "distractors").mkdir(parents=True)

    for path in sorted((BASE_CORPUS / "distractors").glob("*.jsonl")):
        shutil.copyfile(path, out_root / "distractors" / path.name)

    planted: dict[str, dict] = {}
    untouched: list[str] = []

    # Every directory under sessions/, not just the ones that are tasks. `corpus/sessions/smoke/`
    # holds two sessions that belong to no task, and `CorpusManifest.build` globs
    # `sessions/**/*.jsonl`, so the published runs ingested them. Iterating discovered tasks alone
    # dropped both, and the loss was invisible because two plants were added in the same pass and
    # the total came back to 125.
    session_dirs = {p.name for p in (BASE_CORPUS / "sessions").iterdir() if p.is_dir()}
    for task_id in sorted(session_dirs | set(tasks)):
        real = sorted((BASE_CORPUS / "sessions" / task_id).glob("*.jsonl"))
        if task_id not in selection:
            # Every non-selected task keeps its real sessions, so the feed stays the size the
            # published runs used. See the module docstring.
            if real:
                (out_root / "sessions" / task_id).mkdir(parents=True, exist_ok=True)
                untouched.append(task_id)
            for path in real:
                shutil.copyfile(path, out_root / "sessions" / task_id / path.name)
            continue

        if condition == PRESENT:
            # `present` needs no plants.json and no declaration: it is the task's real session
            # and nothing else. Requiring a declaration here would make the condition available
            # only to the tasks somebody has already authored plants for, which is the exact
            # selection bias section 2 of the instrument review found in the harm suite.
            plan = present_plan()
        else:
            spec = load_plants(tasks[task_id].path)
            plan = spec.plan(condition) if spec else None
            if plan is None:
                raise SystemExit(
                    f"{task_id} is in the selection but declares no {condition!r} condition in "
                    f"plants.json. A selected task with no plan would silently keep its true "
                    f"fact and be scored as {condition!r}."
                )

        dates = (
            assign_contradiction_dates(plan.plants, seed)
            if condition == "contradictory"
            else {}
        )
        used = []
        for source in sources_for(plan, task_id, BASE_CORPUS):
            destination = out_root / "sessions" / task_id / source.name
            stem = source.stem
            if stem in dates:
                _write_jsonl(destination, restamp(_read_jsonl(source), dates[stem]))
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            used.append({"file": source.name, "session_date": dates.get(stem)})
        planted[task_id] = {
            "include_real": plan.include_real,
            "plants": [plant.name for plant in plan.plants],
            "wrong_terms": sorted({t for plant in plan.plants for t in plant.wrong_terms}),
            "sessions": used,
        }

    # An empty sessions/<task_id>/ is what `absent` looks like, and git will not carry it. The
    # manifest is built from files, so an absent task simply contributes none.
    manifest = CorpusManifest.build(out_root)
    try:
        base_label = str(BASE_CORPUS.relative_to(REPO))
    except ValueError:
        # A corpus outside the repo is legitimate (a test fixture, a relocated feed). Recording
        # its absolute path is worse provenance than a relative one and far better than crashing.
        base_label = str(BASE_CORPUS)
    provenance = {
        "condition": condition,
        "seed": seed,
        "selection": sorted(selection),
        "planted": planted,
        "tasks_untouched": untouched,
        "sessions_total": len(manifest.sessions),
        "base_corpus": base_label,
    }
    (out_root / "condition.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", required=True, choices=list(CORPUS_CONDITIONS))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--tasks",
        nargs="*",
        help="task ids to place under this condition; default is every task whose "
        "plants.json declares it",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.out is not None:
        output = args.out.resolve()
        conditions_root = CONDITIONS_ROOT.resolve()
        if output == REPO.resolve() or conditions_root not in output.parents:
            raise SystemExit(
                f"--out must be inside {CONDITIONS_ROOT.relative_to(REPO)}; refusing to remove "
                "an arbitrary existing directory"
            )

    if args.tasks:
        # An explicit list is obeyed exactly, including a retired task: assembling one
        # deliberately is legitimate and the caller has said what they want.
        selection = list(args.tasks)
    else:
        # ⛔ The DEFAULT must match what a run would build, and for two days it did not.
        # `scripts/abstention.py` runs `selection_for`, which subtracts RETIRED_TASKS; this CLI
        # used `default_selection` raw, so a hand-assembled `adjacent` corpus carried 16 planted
        # tasks where a real run carries 12. The four extra are the retired ones, and for each of
        # them the corpus WITHHELD the real session and planted over it, so a probe pointed at
        # that corpus was measuring a feed no run produces.
        #
        # Found on 2026-08-30 by two sessions comparing plant ranks and getting answers 45
        # positions apart on `ts-glob-hidden`: one had assembled through this path and the other
        # through the runner's. Imported inside the function because `scripts.abstention` imports
        # this module at load time.
        from scripts.abstention import RETIRED_TASKS

        buildable = default_selection(args.condition)
        selection = [task for task in buildable if task not in RETIRED_TASKS]
        for task in buildable:
            if task in RETIRED_TASKS:
                print(f"[retired] {args.condition}: {task} excluded ({RETIRED_TASKS[task]})")
    if not selection:
        raise SystemExit(
            f"no task declares the {args.condition!r} condition; nothing to assemble"
        )

    out_root = args.out or CONDITIONS_ROOT / args.condition / f"seed-{args.seed}"
    try:
        provenance = assemble(args.condition, args.seed, selection, out_root)
    except PlantSpecError as exc:
        # A missing recording is the ordinary state before a plant is recorded, not a crash.
        raise SystemExit(str(exc)) from None

    print(f"{args.condition} / seed {args.seed} -> {out_root.relative_to(REPO)}")
    print(f"  {provenance['sessions_total']} session files in the feed")
    for task_id, detail in sorted(provenance["planted"].items()):
        kept = "real+" if detail["include_real"] else ""
        names = ",".join(detail["plants"]) or "(nothing)"
        print(f"  {task_id:20s} {kept}{names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
