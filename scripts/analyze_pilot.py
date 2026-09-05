"""Analyse pilot-001 in the preregistered order. Reads artifacts, writes analysis.json.

Endpoints, from preregistration/000-pilot.md: (1) primary recall vs claude_md, per-task
cluster bootstrap CI plus cell McNemar; (2) per-task screening (ceiling and floor);
(3) mechanism (search rate, governing-session-reached); (4) costs; (5) exploratory
bare vs claude_md. Nothing here chooses thresholds: they were committed before the run.

Added afterwards, and not part of that preregistration: (6) the instruction decomposition. Where
the roster carries the `protocol` arm (the baseline bundle plus the shared memory protocol, no
memory layer), `protocol - claude_md` is reported as what the coaching alone bought and
`recall - protocol` as what the store bought on top of it. Every arm's instruction size is reported
beside its success rate, because the two were confounded from `pilot-002` to `pilot-004` and no
results table showed it.

    python -m scripts.analyze_pilot --run-id pilot-001
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

from harness.io import read_jsonl
from harness.reached import mechanism, reached_by_content, reached_by_path
from harness.stats import cluster_bootstrap as _cluster_bootstrap
from harness.stats import effect_concentration, mcnemar_exact
from harness.tasks import discover_tasks

DEFAULT_ARMS = ("bare", "claude_md", "recall")

def _pilot_arms() -> tuple[str, ...]:
    """The runner's own roster, so this analyser cannot fall behind it.

    The import sits inside a function to keep it off this module's top level, but it still runs at
    import time because `SUPPORTED_ARMS` calls it immediately. So it is NOT protection against a
    circular import: if `scripts.pilot` ever imports this module, this breaks and the fix is to
    make `SUPPORTED_ARMS` lazy at its two call sites rather than to move this line.
    """

    from scripts.pilot import ARMS

    return tuple(ARMS)

#: Every arm `scripts/pilot.py` can run, DERIVED from that runner rather than restated here.
#:
#: ⛔ The restated copy is how this list fell behind three times. `protocol` and `fs_grep` were
#: missing long after the runner grew them, so the arm that exists to separate the instruction
#: from the store could be run and then not analysed: `--arms bare,claude_md,protocol,recall`
#: exited `unknown arms`. The comment recording that was written, and the list was NOT made
#: derived, so `mempalace`, `recall_prefetch` and `cognee` went the same way afterwards. A note
#: about a defect is not a fix for it.
#:
#: The import costs about 0.4s and pulls in the adapters, which read their frozen configs and
#: nothing else at import time; no vendor package is touched.
SUPPORTED_ARMS = _pilot_arms()


#: Re-exported so `scripts/discard_sensitivity.py` keeps importing it from here, while there is
#: only ONE implementation. This module used to carry a second copy with seed=42 against
#: harness.stats's 12345, and it computed every published headline interval.
def cluster_bootstrap(per_task_deltas, iterations: int = 10_000, seed: int = 12345):
    interval = _cluster_bootstrap(per_task_deltas, iterations=iterations, seed=seed)
    if interval is not None:
        return interval
    # Every delta identical, so every resample returns that same value. `harness.stats` answers
    # None here because a zero-width interval reads as precision and is the opposite of it; this
    # analyser still has to emit two numbers, so it emits the constant the sample actually holds.
    # NOT (0.0, 0.0): for a survivor subset where every task moved by the same nonzero amount that
    # would report an interval straddling zero for a sample that never touched it.
    values = [float(d) for d in per_task_deltas]
    constant = values[0] if values else 0.0
    return (constant, constant)


def instruction_budget(
    run_dir: Path, records, arms: tuple[str, ...]
) -> dict[str, int | None]:
    """Bytes of memory instruction each arm carried, for publication beside its success rate.

    A success rate is not interpretable without it. Every run from `pilot-002` onward gave `recall`
    5,428 characters, `fs_grep` 231 and `claude_md` none, and no results table said so, so a reader
    comparing the three arms was comparing a memory layer and an instruction budget at once.

    Read from `environment.json`'s manifest where the run wrote one, else from the records, else
    ``None``. Absent is reported as absent rather than as zero: "this arm was told nothing" and
    "nobody wrote it down" are different claims, and runs before 2026-08-29 recorded neither.
    """

    manifest: dict = {}
    env_path = run_dir / "environment.json"
    if env_path.is_file():
        env = json.loads(env_path.read_text(encoding="utf-8"))
        manifest = env.get("instruction_manifest") or {}

    budget: dict[str, int | None] = {}
    for arm in arms:
        entry = manifest.get(arm)
        if isinstance(entry, dict) and entry.get("bytes") is not None:
            budget[arm] = int(entry["bytes"])
            continue
        sizes = {
            int(record.metadata["instruction_bytes"])
            for record in records
            if record.arm == arm and record.metadata.get("instruction_bytes") is not None
        }
        # More than one size within an arm is itself worth seeing, so report the largest rather
        # than picking one silently; the manifest above is the authoritative source.
        budget[arm] = max(sizes) if sizes else None
    return budget


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="pilot-001")
    parser.add_argument(
        "--arms",
        default=",".join(DEFAULT_ARMS),
        help="comma-separated arms in the run; pilot-004 adds placebo",
    )
    parser.add_argument(
        "--results-root",
        default=str(REPO / "results"),
        help="where run directories live; only the tests point this away from results/",
    )
    args = parser.parse_args()
    run_arms = tuple(arm.strip() for arm in args.arms.split(",") if arm.strip())
    unknown = [arm for arm in run_arms if arm not in SUPPORTED_ARMS]
    if unknown:
        raise SystemExit(f"unknown arms {unknown}; choose from {SUPPORTED_ARMS}")
    # Every contrast here is against the designated baseline, and the screens read its rate.
    if "claude_md" not in run_arms:
        raise SystemExit(
            "claude_md is the designated baseline; a roster without it has nothing to contrast "
            "against and no rate to screen tasks on"
        )
    run_dir = Path(args.results_root) / args.run_id

    # The governing fact, from the two places it is already written down: the audited fact_terms,
    # and the authored decision turn that `scripts/build_oracle_bundles.py` extracts. Neither is a
    # new hand-maintained list, which is what keeps the mechanism metric honest.
    fact_terms = {task.task_id: task.fact_terms for task in discover_tasks()}
    evidence: dict[str, str] = {}
    bundles_path = REPO / "corpus" / "oracle_memory" / "bundles.jsonl"
    if bundles_path.is_file():
        for line in bundles_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            bundle = json.loads(line)
            items = bundle.get("items") or []
            if items:
                evidence[str(bundle["task_id"])] = str(items[0].get("evidence_text", ""))

    records = read_jsonl(run_dir / "records.final.jsonl")
    admission = json.loads((run_dir / "admission.json").read_text(encoding="utf-8"))
    discarded = {tuple(cell) for cell in admission["discarded_cells"]}
    admitted = [r for r in records if (r.task_id, r.seed) not in discarded]

    by_cell: dict[tuple[str, int], dict[str, object]] = defaultdict(dict)
    for record in admitted:
        by_cell[record.cell][record.arm] = record

    tasks = sorted({task_id for task_id, _ in by_cell})
    per_task: dict[str, dict[str, list[bool]]] = {
        task: {arm: [] for arm in run_arms} for task in tasks
    }
    for (task_id, _seed), arms in sorted(by_cell.items()):
        for arm in run_arms:
            per_task[task_id][arm].append(bool(arms[arm].success))

    def rate(outcomes: list[bool]) -> float:
        return sum(outcomes) / len(outcomes) if outcomes else float("nan")

    # (2) preregistered screens
    screening = {}
    for task in tasks:
        cmd_r = rate(per_task[task]["claude_md"])
        # `bare` is the floor half of the ceiling screen. A roster without it screens on the
        # baseline alone rather than raising KeyError, which is what an instruction-only roster
        # (`claude_md,protocol,recall`) used to do here.
        has_bare = "bare" in run_arms
        bare_r = rate(per_task[task]["bare"]) if has_bare else float("nan")
        ceiling = cmd_r >= 0.7 or (has_bare and bare_r >= 0.5)
        mech = [
            r
            for r in admitted
            if r.task_id == task and r.arm == "recall" and r.memory_call_count > 0
        ]
        reached = [
            r for r in mech if reached_by_content(r, fact_terms.get(task, ()))[0]
        ]
        reached_path = [r for r in mech if reached_by_path(r)]
        floor = not any(
            per_task[task][arm][i]
            for arm in run_arms
            for i in range(len(per_task[task][arm]))
        ) and len(reached) >= 2
        screening[task] = {
            **{arm: round(rate(per_task[task][arm]), 3) for arm in run_arms},
            "screen": "ceiling" if ceiling else ("floor" if floor else "keep"),
            "recall_searched": len(mech),
            "recall_reached": len(reached),
            "recall_reached_by_path": len(reached_path),
        }

    survivors = [task for task in tasks if screening[task]["screen"] == "keep"]

    def contrast(arm_a: str, arm_b: str, task_set: list[str]):
        deltas = [
            rate(per_task[t][arm_a]) - rate(per_task[t][arm_b]) for t in task_set
        ]
        mean = sum(deltas) / len(deltas)
        lo, hi = cluster_bootstrap(deltas)
        cells_a, cells_b = [], []
        for (task_id, _s), arms in sorted(by_cell.items()):
            if task_id in task_set:
                cells_a.append(bool(arms[arm_a].success))
                cells_b.append(bool(arms[arm_b].success))
        p, only_a, only_b = mcnemar_exact(cells_a, cells_b)
        return {
            "per_task_mean_delta": round(mean, 4),
            "cluster_ci95": [round(lo, 4), round(hi, 4)],
            "mcnemar_p": p,
            "discordant": {"only_" + arm_a: only_a, "only_" + arm_b: only_b},
            "n_tasks": len(task_set),
            "n_cells": len(cells_a),
            # How few tasks carry the mean. A headline delta over 24 tasks that lives on 9 of them
            # is a different claim from one spread across all 24, and the mean cannot tell them
            # apart.
            "concentration": effect_concentration(dict(zip(task_set, deltas, strict=True))),
            "ci_note": (
                "resamples tasks within THIS run; it does not include run-to-run variance, which "
                "the pilot-003/pilot-004 replication measures at r=0.625 across per-task deltas"
            ),
        }

    # (3) mechanism, overall. Three bracketing signals rather than the filename match alone;
    # see harness/reached.py for why the published figure was the loosest of them.
    recall_records = [r for r in admitted if r.arm == "recall"]

    analysis = {
        "run_id": args.run_id,
        "admitted_cells": len(by_cell),
        "discarded_cells": sorted(discarded),
        "arm_success": {
            arm: round(rate([bool(a[arm].success) for a in by_cell.values()]), 3)
            for arm in run_arms
        },
        # Beside the success rate, never in a separate file.
        "arm_instruction_bytes": instruction_budget(run_dir, admitted, run_arms),
        "mechanism": mechanism(recall_records, fact_terms, evidence_by_task=evidence),
        "screening": screening,
        "survivors": survivors,
        "n_survivors": len(survivors),
    }
    if "recall" in run_arms:
        analysis["primary_recall_vs_claude_md_all_tasks"] = contrast(
            "recall", "claude_md", tasks
        )
        analysis["primary_recall_vs_claude_md_survivors"] = (
            contrast("recall", "claude_md", survivors) if survivors else None
        )
    if "bare" in run_arms:
        analysis["exploratory_bare_vs_claude_md"] = contrast("bare", "claude_md", tasks)
    # The decomposition of the headline. `protocol` is the baseline bundle plus the shared memory
    # protocol and no memory layer, so this pair separates what the coaching bought from what the
    # store bought; `recall - claude_md` is their sum and cannot tell them apart.
    if "protocol" in run_arms:
        analysis["instruction_only_protocol_vs_claude_md"] = contrast(
            "protocol", "claude_md", tasks
        )
        if "recall" in run_arms:
            analysis["store_net_of_instruction_recall_vs_protocol"] = contrast(
                "recall", "protocol", tasks
            )
    if "fs_grep" in run_arms:
        analysis["fs_grep_vs_claude_md"] = contrast("fs_grep", "claude_md", tasks)
    if "placebo" in run_arms:
        analysis["placebo_vs_bare"] = contrast("placebo", "bare", tasks)
        analysis["claude_md_vs_placebo"] = contrast("claude_md", "placebo", tasks)
    (run_dir / "analysis.json").write_text(
        json.dumps(analysis, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in analysis.items() if k != "screening"}, indent=2))
    print("\nper-task screening:")
    for task in tasks:
        s = screening[task]
        print(
            f"  {task:<20} "
            + " ".join(f"{arm}={s[arm]:.2f}" for arm in run_arms)
            + f" {s['screen']:<8} "
            f"searched={s['recall_searched']}/3 reached={s['recall_reached']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
