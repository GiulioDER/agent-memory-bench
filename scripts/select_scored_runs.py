"""Keep only the scored run of each model before the analysis reads them (prereg 098, Dev. 2).

    kaggle b t download memory-discipline-trust -o downloads
    kaggle b t download memory-discipline-restraint -o downloads
    python scripts/select_scored_runs.py downloads --out scored
    python scripts/analyze_kaggle_memory.py scored --out results/kaggle-memory-discipline-001

`kaggle b t download` lays runs out as `<task>/<version>/<model>/<run_id>/`. Deviation 2 fixes the
scored run of each model as its EARLIEST complete run on task version 2. That rule is applied here,
per task: for each (task, model) the earliest version-2 run whose items are at most 5% errored or
missing. The driver relaunches only the task that failed, so per task is how "both tasks
completed" has to be read; `pairs` in selection.json records how far apart the two kept runs of
each model started, so a pair taken from different launches is visible rather than assumed away.
The frozen analysis keeps the LATEST reply per item, so without this filter a model run twice
would be scored on its later run.

Everything that decides a model's identity or an item's completeness is read the way
scripts/analyze_kaggle_memory.py reads it, so the two scripts cannot disagree:

- an item file is a run file whose `taskVersion.name` ends in `-item` (content, not file name);
- a model is its `modelVersion.slug` (not the directory name it was downloaded into);
- an item counts as completed only when its state is COMPLETED AND it carries an assistant reply.

Selected run directories are copied unchanged into --out. `selection.json` there records every run
seen and why it was kept or excluded, and every (task, model) with no scored run at all, so the
choice can be audited without rerunning anything.
"""

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ITEMS = json.loads((REPO / "kaggle_memory" / "items.json").read_text(encoding="utf-8"))
SCORED_VERSION = "2"  # Deviation 1: the capped task files are version 2 on Kaggle
MAX_MISSING_SHARE = 0.05
COMPLETED = "BENCHMARK_TASK_RUN_STATE_COMPLETED"
EXPECTED = {f"memory-discipline-{family}": sum(i["family"] == family for i in ITEMS)
            for family in ("trust", "restraint")}
LATEST = datetime.max.replace(tzinfo=UTC)  # a run with no start time sorts after every real one
PAIR_WARN_SECONDS = 3600


def _when(stamp):
    """startTime as a datetime; protobuf JSON varies the fractional digits, so strings misorder."""
    try:
        return datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return LATEST


def _has_reply(data):
    return any(c.get("role") == "CONTENT_ROLE_ASSISTANT"
               for conv in data.get("conversations", []) for req in conv.get("requests", [])
               for c in req.get("contents", []))


def describe(run_dir):
    """(start, completed, slug) for one downloaded run directory."""
    start, completed, slug = "", 0, None
    for p in run_dir.glob("*.run.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        slug = slug or data.get("modelVersion", {}).get("slug")
        if data.get("taskVersion", {}).get("name", "").endswith("-item"):
            completed += data.get("state") == COMPLETED and _has_reply(data)
        else:
            start = data.get("startTime") or start
    return start, completed, slug


def select(root):
    """One dict per run seen, each with `kept` and `reason`."""
    rows = []
    for task_dir in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        expected = EXPECTED.get(task_dir.name)
        if expected is None:
            continue
        for version_dir in sorted(p for p in task_dir.iterdir() if p.is_dir()):
            for model_dir in sorted(p for p in version_dir.iterdir() if p.is_dir()):
                for run_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
                    start, completed, slug = describe(run_dir)
                    rows.append({"task": task_dir.name, "version": version_dir.name,
                                 "model": slug or model_dir.name, "directory": model_dir.name,
                                 "run_id": run_dir.name, "start": start,
                                 "completed": completed, "expected": expected, "path": run_dir})
    chosen = {}
    for row in sorted(rows, key=lambda r: (_when(r["start"]), r["run_id"])):
        key = (row["task"], row["model"])
        if row["version"] != SCORED_VERSION:
            row["kept"], row["reason"] = False, f"task version {row['version']}, not {SCORED_VERSION}"
        elif row["expected"] - row["completed"] > MAX_MISSING_SHARE * row["expected"]:
            row["kept"], row["reason"] = False, (f"incomplete: {row['completed']}/"
                                                 f"{row['expected']} items completed")
        elif key in chosen:
            row["kept"], row["reason"] = False, ("later run of a model already scored "
                                                 f"(run {chosen[key]})")
        else:
            chosen[key] = row["run_id"]
            row["kept"], row["reason"] = True, "earliest complete version-2 run"
    return rows


def unscored(rows):
    """(task, model) pairs seen on version 2 with no kept run: these vanish from the analysis."""
    seen = {(r["task"], r["model"]) for r in rows if r["version"] == SCORED_VERSION}
    kept = {(r["task"], r["model"]) for r in rows if r["kept"]}
    models = {m for _, m in seen}
    return sorted((t, m) for t in EXPECTED for m in models if (t, m) not in kept)


def pairs(rows):
    """For each model with both tasks kept, the gap in seconds between the two runs' starts."""
    kept = {(r["task"], r["model"]): _when(r["start"]) for r in rows if r["kept"]}
    out = {}
    for model in sorted({m for _, m in kept}):
        starts = [kept.get((t, model)) for t in EXPECTED]
        if all(s is not None and s != LATEST for s in starts):
            out[model] = abs((starts[0] - starts[1]).total_seconds())
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("downloads")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise SystemExit(f"{out} exists and is not an empty directory; refusing to mix selections")
    rows = select(args.downloads)
    if not rows:
        raise SystemExit(f"no runs under {args.downloads}")
    for row in rows:
        if row["kept"]:
            dest = out / row["task"] / row["version"] / row["directory"] / row["run_id"]
            shutil.copytree(row["path"], dest)
    out.mkdir(parents=True, exist_ok=True)
    missing, gaps = unscored(rows), pairs(rows)
    record = {"runs": [{k: v for k, v in row.items() if k != "path"} for row in rows],
              "unscored": [{"task": t, "model": m} for t, m in missing],
              "pairs": gaps}
    (out / "selection.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8",
                                        newline="\n")
    kept = [r for r in rows if r["kept"]]
    print(f"kept {len(kept)} runs of {len(rows)}")
    for row in rows:
        if not row["kept"] and row["version"] == SCORED_VERSION:
            print(f"  excluded {row['task']} {row['model']} run {row['run_id']}: {row['reason']}")
    for task, model in missing:
        print(f"  NO SCORED RUN: {task} {model} (reported as not run, not dropped)")
    for model, gap in gaps.items():
        if gap > PAIR_WARN_SECONDS:
            print(f"  PAIR FROM DIFFERENT LAUNCHES: {model}, starts {gap / 3600:.1f} h apart")
    return 0


if __name__ == "__main__":
    sys.exit(main())
