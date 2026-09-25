"""Analyse a memory-discipline run downloaded from Kaggle Benchmarks (preregistration 098).

    kaggle b t download memory-discipline-trust -o <dir>
    kaggle b t download memory-discipline-restraint -o <dir>
    python scripts/analyze_kaggle_memory.py <dir> --out results/kaggle-memory-discipline-001

Every per-item `*.run.json` under <dir> is RE-SCORED from its raw reply with
`kaggle_memory.scoring`, rather than trusting the result the notebook recorded, and each item is
identified by its exact prompt text, so a run of a different item set fails loudly instead of
being scored against the wrong readings. Disagreements with the in-notebook result are counted and
reported; the preregistration says there should be none.
"""

import argparse
import json
import math
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from kaggle_memory.scoring import (
    RESTRAINT_CONDITIONS,
    TRUST_CONDITIONS,
    classify,
    condition_accuracy,
    discipline_score,
)

ITEMS = json.loads((REPO / "kaggle_memory" / "items.json").read_text(encoding="utf-8"))
BY_PROMPT = {item["prompt"]: item for item in ITEMS}
BY_ID = {item["item_id"]: item for item in ITEMS}
COMPLETED = "BENCHMARK_TASK_RUN_STATE_COMPLETED"
MAX_ERRORED_SHARE = 0.05
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260925
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _texts(content):
    return "\n".join(part.get("text", "") for part in content.get("parts", []))


def _when(stamp):
    """endTime as a datetime; protobuf JSON varies the fractional digits, so strings misorder."""
    try:
        return datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return EPOCH


def read_run(path):
    """One per-item run file as {model, item_id, state, reply, recorded, end}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    contents = [c for conv in data.get("conversations", []) for req in conv.get("requests", [])
                for c in req.get("contents", [])]
    prompts = [_texts(c) for c in contents if c.get("role") == "CONTENT_ROLE_USER"]
    replies = [_texts(c) for c in contents if c.get("role") == "CONTENT_ROLE_ASSISTANT"]
    item_id = None
    if prompts:
        if prompts[0] not in BY_PROMPT:
            raise SystemExit(f"{path}: prompt matches no item in items.json; wrong item set?")
        item_id = BY_PROMPT[prompts[0]]["item_id"]
    recorded = next((r.get("dictResult") for r in data.get("results", [])
                     if r.get("dictResult")), None)
    if item_id is None and recorded:
        item_id = recorded.get("item_id")
    model = data.get("modelVersion", {}).get("slug")
    if not model:
        # Without a slug every model would collapse into one and dedup would keep one reply per
        # item across all of them, silently.
        raise SystemExit(f"{path}: no modelVersion.slug; cannot attribute this run to a model")
    # All assistant text, in order: a reply split across contents (thinking, then answer) is
    # scored whole, and the parser's own precedence picks the directive.
    return {"model": model, "item_id": item_id,
            "state": data.get("state"), "reply": "\n".join(replies) if replies else None,
            "recorded": recorded, "end": data.get("endTime") or ""}


def collect(root):
    """Latest completed run per (model, item); items with no completed run count as errored."""
    best = {}
    for path in sorted(Path(root).rglob("*.run.json")):
        head = json.loads(path.read_text(encoding="utf-8")).get("taskVersion", {})
        if not head.get("name", "").endswith("-item"):
            continue
        run = read_run(path)
        if run["item_id"] is None:
            continue
        key = (run["model"], run["item_id"])
        rank = (run["state"] == COMPLETED and run["reply"] is not None, _when(run["end"]))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, run)
    return [run for _, run in best.values()]


def wilson(hit, n, z=1.959964):
    if n == 0:
        return (float("nan"), float("nan"))
    p = hit / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centre - half, centre + half)


def cluster_bootstrap(results, statistic):
    """95% interval for `statistic` resampling SCENARIOS, the unit the items are nested in."""
    by_scenario = {}
    for row in results:
        by_scenario.setdefault(BY_ID[row["item_id"]]["scenario_id"], []).append(row)
    clusters = list(by_scenario.values())
    rng = random.Random(BOOTSTRAP_SEED)
    draws = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = [row for _ in clusters for row in rng.choice(clusters)]
        value = statistic(sample)
        if not math.isnan(value):
            draws.append(value)
    if not draws:
        # A model with no completed items has no interval; it must not crash the whole report.
        return (float("nan"), float("nan"))
    draws.sort()
    return (draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1])


def _rate(rows, predicate):
    rows = list(rows)
    return sum(map(predicate, rows)) / len(rows) if rows else float("nan")


def analyse_model(runs):
    results, disagreements, errored = [], 0, {"trust": 0, "restraint": 0}
    for run in runs:
        item = BY_ID[run["item_id"]]
        if run["state"] != COMPLETED or run["reply"] is None:
            errored[item["family"]] += 1
            continue
        row = classify(item, run["reply"])
        if run["recorded"] and bool(run["recorded"].get("correct")) != row["correct"]:
            disagreements += 1
        results.append(row)
    size = {family: sum(i["family"] == family for i in ITEMS) for family in errored}
    seen = {BY_ID[r["item_id"]]["family"] for r in runs}
    missing = {f: size[f] - sum(BY_ID[r["item_id"]]["family"] == f for r in runs) for f in size}
    incomplete = {f: (errored[f] + missing[f]) / size[f] > MAX_ERRORED_SHARE for f in size}
    table = condition_accuracy(results)
    score = discipline_score(results)
    sup = [r for r in results if r["condition"] == "superseded"]
    contra_asks = [r for r in results if r["condition"] == "contradictory" and r["outcome"] == "ask"]
    return {
        "families_seen": sorted(seen),
        "errored": errored,
        "missing": missing,
        "incomplete": incomplete,
        "rescoring_disagreements": disagreements,
        "by_condition": {c: {"correct": hit, "n": n, "accuracy": hit / n, "wilson95": wilson(hit, n)}
                         for c, (hit, n) in table.items()},
        "trust": score["trust"],
        "restraint": score["restraint"],
        "score": score["score"],
        "j": score["j"],
        "j_ci95": cluster_bootstrap(results, lambda rows: discipline_score(rows)["j"]),
        "superseded_explicit": _rate((r for r in sup if BY_ID[r["item_id"]]["variant"] == "explicit"),
                                     lambda r: r["correct"]),
        "superseded_implicit": _rate((r for r in sup if BY_ID[r["item_id"]]["variant"] == "implicit"),
                                     lambda r: r["correct"]),
        "stale_rate_stale_first": _rate(
            (r for r in sup if BY_ID[r["item_id"]]["order"] == "stale_first"),
            lambda r: r["outcome"] == "value:stale"),
        "stale_rate_current_first": _rate(
            (r for r in sup if BY_ID[r["item_id"]]["order"] == "current_first"),
            lambda r: r["outcome"] == "value:stale"),
        "over_ask_present": _rate((r for r in results if r["condition"] == "present"),
                                  lambda r: r["outcome"] == "ask"),
        "contradictory_asks_naming_both": _rate(contra_asks, lambda r: r["names_both_sides"]),
        "outcomes": {c: _count(r["outcome"] for r in results if r["condition"] == c)
                     for c in TRUST_CONDITIONS + RESTRAINT_CONDITIONS},
        "items": results,
    }


def _count(labels):
    counts = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def analyse(root):
    runs = collect(root)
    models = sorted({run["model"] for run in runs})
    return {model: analyse_model([r for r in runs if r["model"] == model]) for model in models}


def _json_safe(value):
    """NaN and infinities as null, so report.json is strict JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _fmt(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.3f}"


def markdown(report):
    header = ("| model | trust | restraint | J | J 95% CI | present | superseded | absent | "
              "adjacent | contradictory | complete |")
    lines = [header, "|---" * 11 + "|"]
    ranked = sorted(report.items(), key=lambda kv: -kv[1]["j"] if not math.isnan(kv[1]["j"])
                    else math.inf)
    for model, m in ranked:
        acc = {c: m["by_condition"].get(c, {}).get("accuracy") for c in
               ("present", "superseded", "absent", "adjacent", "contradictory")}
        lo, hi = m["j_ci95"]
        lines.append(
            f"| {model} | {_fmt(m['trust'])} | {_fmt(m['restraint'])} | {_fmt(m['j'])} | "
            f"[{_fmt(lo)}, {_fmt(hi)}] | "
            + " | ".join(_fmt(acc[c]) for c in acc)
            + f" | {'no' if any(m['incomplete'].values()) else 'yes'} |"
            + (f" rescoring disagreements: {m['rescoring_disagreements']}"
               if m["rescoring_disagreements"] else ""))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("downloads")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = analyse(args.downloads)
    if not report:
        raise SystemExit(f"no per-item run files under {args.downloads}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(_json_safe(report), indent=1, allow_nan=False)
                                     + "\n", encoding="utf-8",
                                     newline="\n")
    (out / "report.md").write_text(markdown(report), encoding="utf-8", newline="\n")
    print(markdown(report))
    disagreements = {m: r["rescoring_disagreements"] for m, r in report.items()
                     if r["rescoring_disagreements"]}
    if disagreements:
        # Preregistration 098: the in-notebook scorer is this scorer, so any disagreement means
        # the reply was extracted differently. The report is written, but the run is not clean.
        print(f"RESCORING DISAGREEMENTS: {disagreements}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
