"""Two-panel dot chart of trust and restraint per model, from the frozen analysis output.

    python scripts/plot_kaggle_memory.py results/kaggle-memory-discipline-001/report.json OUT.png

Models are ranked by J (best at the top). Both panels share the 0 to 1 scale on purpose: the
finding is that trust is bunched at the right while restraint is spread out, and a zoomed trust
axis would hide exactly that. gpt-oss-120b is drawn hollow because its scored run carries the
retrieval flag in preregistration 098.
"""

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FLAGGED = {"openai/gpt-oss-120b"}
INK, MUTED, DOT = "#1f2328", "#8c959f", "#0969da"


def short(model):
    name = model.split("/", 1)[1]
    for suffix in ("@default", "@20251001", "@20251101", "@20250929", "-2026-03-05",
                   "-2026-03-17", "-2026-04-23", "-2507", "-0309"):
        name = name.replace(suffix, "")
    return name


def main(report_path, out_path):
    report = json.load(open(report_path, encoding="utf-8"))
    rows = sorted(report.items(), key=lambda kv: kv[1]["j"])  # worst first: bottom of the chart
    labels = [f"{short(m)}  (J {r['j']:.2f})" for m, r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(10, 11), sharey=True, dpi=160)
    for ax, key, title in ((axes[0], "trust", "Trust: uses memory when it holds the answer"),
                           (axes[1], "restraint", "Restraint: asks when it does not")):
        for y, (model, r) in enumerate(rows):
            hollow = model in FLAGGED
            ax.plot([0, r[key]], [y, y], color="#d0d7de", lw=1, zorder=1)
            ax.scatter(r[key], y, s=36, zorder=2, color="white" if hollow else DOT,
                       edgecolors=DOT, linewidths=1.5)
        ax.set_xlim(0, 1.02)
        ax.set_title(title, fontsize=11, color=INK, loc="left")
        ax.grid(axis="x", color="#eaeef2", lw=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=8)
    axes[0].set_yticks(range(len(rows)))
    axes[0].set_yticklabels(labels, fontsize=8, color=INK)
    fig.suptitle(f"Same memory, {len(rows)} models (ranked by J = trust + restraint - 1)",
                 fontsize=13, color=INK, x=0.02, ha="left")
    fig.text(0.02, 0.01, "Kaggle Benchmarks, 216 items per model, preregistration 098. "
             "Hollow dot: scored run carries a retrieval caveat.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(out_path, facecolor="white")


if __name__ == "__main__":
    main(*sys.argv[1:3])
