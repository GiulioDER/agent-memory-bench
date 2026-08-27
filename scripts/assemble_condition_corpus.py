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
from harness.damage import CONDITIONS
from harness.plants import (
    PlantSpecError,
    assign_contradiction_dates,
    load_plants,
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


def assemble(condition: str, seed: int, selection: list[str], out_root: Path) -> dict:
    if condition not in CONDITIONS:
        raise SystemExit(f"unknown condition {condition!r}; expected one of {CONDITIONS}")

    tasks = {task.task_id: task for task in discover_tasks()}
    unknown = [task_id for task_id in selection if task_id not in tasks]
    if unknown:
        raise SystemExit(f"unknown task(s) in selection: {unknown}")

    if out_root.exists():
        shutil.rmtree(out_root)
    (out_root / "sessions").mkdir(parents=True)
    (out_root / "distractors").mkdir(parents=True)

    for path in sorted((BASE_CORPUS / "distractors").glob("*.jsonl")):
        shutil.copyfile(path, out_root / "distractors" / path.name)

    planted: dict[str, dict] = {}
    untouched: list[str] = []

    for task_id in sorted(tasks):
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

        spec = load_plants(tasks[task_id].path)
        plan = spec.plan(condition) if spec else None
        if plan is None:
            raise SystemExit(
                f"{task_id} is in the selection but declares no {condition!r} condition in "
                f"plants.json. A selected task with no plan would silently keep its true fact "
                f"and be scored as {condition!r}."
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
    parser.add_argument("--condition", required=True, choices=list(CONDITIONS))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--tasks",
        nargs="*",
        help="task ids to place under this condition; default is every task whose "
        "plants.json declares it",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.tasks:
        selection = list(args.tasks)
    else:
        selection = []
        for task in discover_tasks():
            spec = load_plants(task.path)
            if spec and spec.plan(args.condition):
                selection.append(task.task_id)
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
