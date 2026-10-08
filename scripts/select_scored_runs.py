"""Keep only the scored run of each model before the analysis reads them (prereg 098, Dev. 2).

    kaggle b t download memory-discipline-trust -o downloads
    kaggle b t download memory-discipline-restraint -o downloads
    python scripts/select_scored_runs.py downloads --out scored
    python scripts/analyze_kaggle_memory.py scored --out results/kaggle-memory-discipline-001

`kaggle b t download` lays runs out as `<task>/<version>/<model>/<run_id>/`. Deviation 2 fixes the
scored run of each model as its EARLIEST complete run on task version 2. That rule is applied here,
per task: for each (task, model) the earliest version-2 run whose items are at most 5% errored or
missing. The driver relaunches only the task that failed, so per task is how "both tasks
completed" has to be read. The frozen analysis keeps the LATEST reply per item, so without this
filter a model run twice would be scored on its later run.

Selected run directories are copied unchanged into --out. `selection.json` there records every run
seen and why it was kept or excluded, so the choice can be audited without rerunning anything.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ITEMS = json.loads((REPO / "kaggle_memory" / "items.json").read_text(encoding="utf-8"))
SCORED_VERSION = "2"  # Deviation 1: the capped task files are version 2 on Kaggle
MAX_MISSING_SHARE = 0.05
COMPLETED = "BENCHMARK_TASK_RUN_STATE_COMPLETED"
EXPECTED = {f"memory-discipline-{family}": sum(i["family"] == family for i in ITEMS)
            for family in ("trust", "restraint")}


def describe(run_dir):
    """Start time and item completeness of one downloaded run directory.

    Item files are told from the task's own run file by CONTENT (`taskVersion.name` ending in
    `-item`), exactly as scripts/analyze_kaggle_memory.py tells them, never by file name, so the
    two scripts cannot disagree about which files are items.
    """
    start, completed = "", 0
    for p in run_dir.glob("*.run.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("taskVersion", {}).get("name", "").endswith("-item"):
            completed += data.get("state") == COMPLETED
        else:
            start = data.get("startTime") or start
    return start, completed


def select(root):
    """[(task, version, model, run_id, start, completed, expected, kept, reason)]."""
    rows = []
    for task_dir in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        expected = EXPECTED.get(task_dir.name)
        if expected is None:
            continue
        for version_dir in sorted(p for p in task_dir.iterdir() if p.is_dir()):
            for model_dir in sorted(p for p in version_dir.iterdir() if p.is_dir()):
                for run_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
                    start, completed = describe(run_dir)
                    rows.append({"task": task_dir.name, "version": version_dir.name,
                                 "model": model_dir.name, "run_id": run_dir.name,
                                 "start": start, "completed": completed,
                                 "expected": expected, "path": run_dir})
    chosen = {}
    for row in sorted(rows, key=lambda r: (r["start"] or "~", r["run_id"])):
        if row["version"] != SCORED_VERSION:
            row["kept"], row["reason"] = False, f"task version {row['version']}, not {SCORED_VERSION}"
        elif row["expected"] - row["completed"] > MAX_MISSING_SHARE * row["expected"]:
            row["kept"], row["reason"] = False, (f"incomplete: {row['completed']}/"
                                                 f"{row['expected']} items completed")
        elif (row["task"], row["model"]) in chosen:
            row["kept"], row["reason"] = False, ("later run of a model already scored "
                                                 f"(run {chosen[(row['task'], row['model'])]})")
        else:
            chosen[(row["task"], row["model"])] = row["run_id"]
            row["kept"], row["reason"] = True, "earliest complete version-2 run"
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("downloads")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty; refusing to mix selections")
    rows = select(args.downloads)
    if not rows:
        raise SystemExit(f"no runs under {args.downloads}")
    for row in rows:
        if row["kept"]:
            dest = out / row["task"] / row["version"] / row["model"] / row["run_id"]
            shutil.copytree(row["path"], dest)
    out.mkdir(parents=True, exist_ok=True)
    record = [{k: v for k, v in row.items() if k != "path"} for row in rows]
    (out / "selection.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8",
                                        newline="\n")
    kept = [r for r in rows if r["kept"]]
    print(f"kept {len(kept)} runs of {len(rows)}")
    for row in rows:
        if not row["kept"] and row["version"] == SCORED_VERSION:
            print(f"  excluded {row['task']} {row['model']} run {row['run_id']}: {row['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
