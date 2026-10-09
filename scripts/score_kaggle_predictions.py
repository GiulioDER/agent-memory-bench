"""Score the ten predictions of preregistration 098 against the frozen analysis output.

    python scripts/score_kaggle_predictions.py results/kaggle-memory-discipline-001/report.json

Reads only report.json, which scripts/analyze_kaggle_memory.py (frozen) wrote; computes nothing
the analysis did not already compute per model, only the medians and pooled figures the
predictions name. Median and pooled figures are over complete models only (Predictions,
preamble). "Pooled" is the mean over complete models, the definition endpoint 4 gives; where a
prediction could also be read item-weighted, that reading is printed beside it, and the scorecard
says if the two readings disagree on met or missed.

Writes predictions.json next to report.json and prints a markdown table.
"""

import json
import statistics
import sys
from pathlib import Path

CONDITIONS = ("present", "superseded", "absent", "adjacent", "contradictory")


def complete_models(report):
    return {m: r for m, r in report.items() if not any(r["incomplete"].values())}


def acc(r, condition):
    return r["by_condition"][condition]["accuracy"]


def score(report):
    models = complete_models(report)
    rows = list(models.values())
    med = {c: statistics.median(acc(r, c) for r in rows) for c in CONDITIONS}
    js = sorted((r["j"] for r in rows), reverse=True)
    out = []

    def add(n, claim, threshold, measured, met, alt=None):
        out.append({"n": n, "claim": claim, "threshold": threshold, "measured": measured,
                    "met": met, "item_weighted": alt})

    add(1, "Present is easy", "median present accuracy >= 0.90",
        f"{med['present']:.3f}", med["present"] >= 0.90)

    others = {c: v for c, v in med.items() if c != "contradictory"}
    add(2, "Contradictory is the hardest condition",
        "median contradictory accuracy below the median of every other condition",
        "contradictory " + f"{med['contradictory']:.3f}; "
        + ", ".join(f"{c} {v:.3f}" for c, v in others.items()),
        all(med["contradictory"] < v for v in others.values()))

    diffs = [r["superseded_explicit"] - r["superseded_implicit"] for r in rows]
    pooled = statistics.mean(diffs)
    share = sum(d >= 0 for d in diffs) / len(diffs)
    add(3, "Implicit supersession is harder than explicit",
        "pooled (explicit - implicit) in [+0.03, +0.20] AND explicit >= implicit for >= 70% of models",
        f"pooled {pooled:+.3f}; explicit >= implicit for {share:.0%} of models",
        0.03 <= pooled <= 0.20 and share >= 0.70)

    sf = statistics.mean(r["stale_rate_stale_first"] for r in rows)
    cf = statistics.mean(r["stale_rate_current_first"] for r in rows)
    add(4, "Position pulls toward the stale memo (low confidence)",
        "pooled stale rate in current_first >= stale_first + 0.02",
        f"current_first {cf:.3f}, stale_first {sf:.3f}", cf >= sf + 0.02)

    med_j = statistics.median(js)
    add(5, "Range", "best J in [0.60, 0.95] AND median J in [0.30, 0.75]",
        f"best {js[0]:.3f}, median {med_j:.3f}",
        0.60 <= js[0] <= 0.95 and 0.30 <= med_j <= 0.75)

    cred = sorted(m for m, r in models.items() if r["trust"] >= 0.85 and r["restraint"] <= 0.60)
    timid = sorted(m for m, r in models.items() if r["restraint"] >= 0.85 and r["trust"] <= 0.70)
    add(6, "Two failure profiles exist, not one skill",
        ">= 1 credulous (trust >= 0.85, restraint <= 0.60) AND >= 1 timid (restraint >= 0.85, trust <= 0.70)",
        f"credulous {cred or 'none'}; timid {timid or 'none'}", bool(cred) and bool(timid))

    over = statistics.median(r["over_ask_present"] for r in rows)
    add(7, "Over-asking is rare", "median over-ask rate on present <= 0.05",
        f"{over:.3f}", over <= 0.05)

    named = [r["contradictory_asks_naming_both"] for r in rows
             if r["contradictory_asks_naming_both"] is not None]
    asks = [r["outcomes"]["contradictory"].get("ask", 0) for r in rows
            if r["contradictory_asks_naming_both"] is not None]
    pooled8 = statistics.mean(named)
    weighted8 = sum(s * a for s, a in zip(named, asks)) / sum(asks)
    add(8, "A conflict, when reported, is reported properly",
        "pooled share of contradictory ASK replies naming both values >= 0.60",
        f"{pooled8:.3f}", pooled8 >= 0.60, f"{weighted8:.3f} (met={weighted8 >= 0.60})")

    add(9, "The lure costs more than the void (low confidence)",
        "median adjacent accuracy <= median absent accuracy",
        f"adjacent {med['adjacent']:.3f}, absent {med['absent']:.3f}",
        med["adjacent"] <= med["absent"])

    def ff(r):
        total = sum(sum(o.values()) for o in r["outcomes"].values())
        fails = sum(o.get("format_failure", 0) for o in r["outcomes"].values())
        return fails, total

    pooled10 = statistics.mean(f / t for f, t in map(ff, rows))
    fails, total = map(sum, zip(*map(ff, rows)))
    add(10, "The format is not the obstacle", "pooled format_failure rate <= 0.02",
        f"{pooled10:.4f}", pooled10 <= 0.02, f"{fails / total:.4f} (met={fails / total <= 0.02})")

    near_zero = sum(abs(j) <= 0.05 for j in js)
    falsifiers = {
        "complete_models": len(rows),
        "models_within_0.05_of_J0": near_zero,
        "design_falsified_by_trivial_policies": near_zero > len(rows) / 2,
        "rescoring_disagreements": sum(r["rescoring_disagreements"] for r in rows),
    }
    return out, falsifiers


def main(argv=None):
    path = Path((argv or sys.argv[1:])[0])
    predictions, falsifiers = score(json.loads(path.read_text(encoding="utf-8")))
    (path.parent / "predictions.json").write_text(
        json.dumps({"predictions": predictions, "falsifiers": falsifiers}, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    print("| # | prediction | threshold | measured | result |")
    print("|---|---|---|---|---|")
    for p in predictions:
        extra = f" (item-weighted {p['item_weighted']})" if p["item_weighted"] else ""
        print(f"| {p['n']} | {p['claim']} | {p['threshold']} | {p['measured']}{extra} | "
              f"{'met' if p['met'] else 'missed'} |")
    print(json.dumps(falsifiers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
