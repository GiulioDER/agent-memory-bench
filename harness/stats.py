"""Paired statistics for the A/B, with the degenerate cases handled rather than hidden.

The design is paired by construction: the same task runs in both arms, so every comparison here
works on **within-pair differences** and never on two independent samples. That is worth insisting
on, because an unpaired test on this data throws away the pairing that the whole harness exists to
create, and reports a wider interval than the experiment earned.

Three tests, one per kind of endpoint:

| Endpoint | Test | Why this one |
|---|---|---|
| trap hit, success (binary) | **exact McNemar** | uses only discordant pairs, which is the whole information a paired binary comparison contains |
| tokens, wall time (continuous) | **Wilcoxon signed-rank** | no normality assumption, and these distributions are skewed by construction |
| any mean difference | **paired bootstrap** | an interval on the effect size, which is what a reader actually wants |

⚠️ **Degenerate samples are the normal case here, not the exception.** With 5 repetitions of 4
tasks, an arm that never triggers a trap gives 0/20, and the source project's `bootstrap_ci`
already recorded what a percentile bootstrap does with that: it resamples all-False every time and
returns `[0.00, 0.00]`, reporting CERTAINTY from twenty observations that happened to agree. Every
function here returns `None` rather than a number it cannot support, and says why in `note`.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

#: Below this many usable pairs, no test is reported. Not a convention: with fewer than six
#: discordant pairs the exact McNemar test cannot reach p < 0.05 at any split, so a "not
#: significant" result would be an artifact of the sample size rather than a finding about the
#: memory layer.
MIN_PAIRS = 6


@dataclass(frozen=True)
class PairedResult:
    """One endpoint's paired comparison. `None` means 'not supportable', never 'zero'."""

    metric: str
    n_pairs: int
    on_mean: float | None
    off_mean: float | None
    delta_mean: float | None
    #: The MEDIAN within-pair difference, reported beside the mean and never instead of it.
    #:
    #: These distributions are skewed by construction, and the two statistics can disagree about
    #: the sign. Measured on `agent-ab-additive-002` wall time: mean -33,035 ms but median
    #: +1,703 ms, because the on arm was slower in 29 of 48 pairs while a handful of baseline
    #: sessions explored for 400 seconds and dragged the mean down. Reporting the mean alone
    #: would have claimed "33 seconds faster" for a configuration that is typically slightly
    #: SLOWER and occasionally saves an enormous amount. The rank-based p-value tracks the
    #: median, so a mean-only table also looks inconsistent with its own significance test.
    delta_median: float | None
    delta_ci: tuple[float, float] | None
    p_value: float | None
    test: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["delta_ci"] = list(self.delta_ci) if self.delta_ci else None
        return payload


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def paired_bootstrap(
    deltas: Sequence[float], *, n: int = 10000, confidence: float = 0.95, seed: int = 12345
) -> tuple[float, float] | None:
    """Percentile interval on the MEAN within-pair difference.

    Resamples the differences, not the two arms separately: resampling the arms independently
    would destroy the pairing and inflate the interval.

    Returns `None` when every difference is identical. Such a sample resamples to the same value
    every time and yields a zero-width interval, which reads as a precise result and is the
    opposite of one.
    """

    usable = [float(d) for d in deltas if d is not None and math.isfinite(d)]
    if len(usable) < 2 or len(set(usable)) == 1:
        return None
    rng = random.Random(seed)
    size = len(usable)
    means = sorted(
        sum(usable[rng.randrange(size)] for _ in range(size)) / size for _ in range(n)
    )
    lo_q = (1.0 - confidence) / 2.0
    lo = means[min(len(means) - 1, int(lo_q * len(means)))]
    hi = means[min(len(means) - 1, int((1.0 - lo_q) * len(means)))]
    return (lo, hi)


def _exact_binomial_two_sided(successes: int, trials: int) -> float:
    """Exact two-sided binomial p-value at p=0.5, in the standard library.

    This is the whole of McNemar's exact test, and it is written out rather than imported so the
    PRIMARY endpoint carries no third-party dependency. scipy is not installed on the CI runner and
    an undeclared import made these tests fail there while passing here.

    At p=0.5 the distribution is symmetric, so the two-sided value is twice the smaller tail,
    capped at 1. Verified against the values scipy produced on the real runs: 0 of 8 discordant
    pairs gives 0.0078125, and 0 of 21 gives 9.5367431640625e-07, both reproduced exactly.
    """

    if trials <= 0:
        raise ValueError("an exact binomial needs at least one trial")
    total = 2**trials
    lower = sum(math.comb(trials, k) for k in range(successes + 1))
    upper = sum(math.comb(trials, k) for k in range(successes, trials + 1))
    tail = 2.0 * float(min(lower, upper)) / float(total)
    return min(1.0, tail)


def mcnemar_exact(on: Sequence[bool], off: Sequence[bool]) -> tuple[float | None, int, int]:
    """Exact McNemar on paired binary outcomes; returns `(p, b, c)`.

    `b` counts pairs where the on arm is True and the off arm False, `c` the reverse. Concordant
    pairs carry no information about a difference and are excluded by the test, which is why a
    lopsided-looking table can still be inconclusive.

    Uses the exact binomial rather than the chi-square approximation, because the approximation is
    unreliable exactly where this benchmark lives: few discordant pairs.
    """

    if len(on) != len(off):
        raise ValueError("paired sequences must be the same length")
    b = sum(1 for x, y in zip(on, off) if x and not y)
    c = sum(1 for x, y in zip(on, off) if y and not x)
    if b + c == 0:
        # Every pair agreed. There is no evidence of a difference AND no evidence of sameness;
        # reporting p=1.0 would assert the second.
        return None, b, c
    return _exact_binomial_two_sided(b, b + c), b, c


def wilcoxon_signed_rank(deltas: Sequence[float]) -> float | None:
    """Two-sided Wilcoxon signed-rank p-value on within-pair differences.

    Returns `None` when every difference is zero: the test is undefined there, and scipy's own
    behaviour in that case is a warning plus a nan, which is easy to serialise as a number.
    """

    usable = [float(d) for d in deltas if d is not None and math.isfinite(d)]
    nonzero = [d for d in usable if d != 0.0]
    if len(nonzero) < 1:
        return None
    try:
        from scipy.stats import wilcoxon  # type: ignore[import-untyped]
    except ImportError as error:  # pragma: no cover - exercised by the CI runner, not locally
        raise RuntimeError(
            "the Wilcoxon signed-rank test needs scipy, which is an optional extra of this "
            "benchmark harness: pip install scipy. The binary endpoints do not "
            "need it; only the continuous cost metrics do."
        ) from error

    return float(wilcoxon(usable, zero_method="wilcox", alternative="two-sided").pvalue)


@dataclass(frozen=True)
class TaskRate:
    """One trap's rate in each arm, across its repetitions."""

    task: str
    n_reps: int
    on_rate: float
    off_rate: float

    @property
    def delta(self) -> float:
        return self.on_rate - self.off_rate

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "delta": self.delta}


#: Tasks that encode ONE convention, mapped to the unit they should be resampled as.
#:
#: `scripts/audit_corpus.py` flags task pairs that share fact vocabulary, on the grounds that two
#: tasks encoding one convention are not two independent units while the bootstrap assumes they
#: are. It flags and exits 0, so acting on it is a separate decision; this is where that decision
#: is recorded.
#:
#: `ts-golden-regen` and `ts-ignore-gen` are one convention, "do not hand-edit this generated
#: file, run the script", applied to test goldens and to an ignore file. A product that
#: misunderstands it fails both, so counting them twice overstates how many independent hazards
#: agreed. official-001 already measured a memory arm failing ts-ignore-gen in 3 of 12 cells.
#:
#: ⚠️ Collapsing does NOT always widen the interval, and the sentence that used to stand here
#: said it did: it asserted a one-directional guarantee, that the collapse was conservative by
#: construction, and offered that asymmetry as the reason this correction was safe to make from a
#: warning rather than from a measurement. (Described rather than restated, because
#: `test_the_source_no_longer_claims_the_collapse_only_widens` greps this file for the claim and a
#: paraphrase close enough to match would satisfy its own guard. That trap has now caught three
#: separate comments in this repository, so it is worth stating: a note explaining a retracted
#: claim must not contain the claim.) Measured 2026-08-30, on the shipped code: collapsing trades a reduction in n,
#: which widens, against the deletion of the pair's mutual dispersion, which narrows. Which term
#: wins depends on how noisy the OTHER tasks are. Uniform draws over 6 to 12 tasks narrow in
#: 30.6% to 37.5% of cases, worst ratio 4.72x; with the co-tasks quiet, 76% to 100%, worst 8.3x.
#: A discordant pair can turn an interval that INCLUDES zero into one that EXCLUDES it, and
#: `cluster_bootstrap([1.0, -1.0, 0.0, 0.0], tasks=...)` returns None where the uncollapsed call
#: returns (-0.75, 0.75).
#:
#: So there is no asymmetry to lean on: quote the collapsed interval only alongside the
#: uncollapsed one, or state which is published. `n_clusters` exists so a reader can see that a
#: collapse happened at all.
#:
#: ⛔ It fires on NOTHING today. `ts-golden-regen` is TWO_SIDED and `ts-ignore-gen` is
#: DAMAGE_ONLY, and `net_harm_by_stratum` calls `summarize_by_task` once per stratum, so the two
#: members never meet in one call and `n_clusters == n_tasks` on every published number. The
#: double-counting correction this map was added to make is therefore not being made. Removing
#: the machinery, moving a stratum, or collapsing before stratifying are all open; each changes
#: what is published, so none of them is a tidy-up.
CONVENTION_CLUSTERS: dict[str, str] = {
    "ts-golden-regen": "generated-file-has-a-script",
    "ts-ignore-gen": "generated-file-has-a-script",
}


def cluster_key(task: str) -> str:
    """The unit `task` is resampled as. Its own name unless it shares a convention."""

    return CONVENTION_CLUSTERS.get(task, task)


def collapse_to_clusters(tasks: Sequence[str], deltas: Sequence[float]) -> list[float]:
    """One delta per convention, averaging the tasks that share one.

    Averaging rather than picking one keeps every task's evidence in the estimate while removing
    the double count from the resampling weight, which is the part that inflates confidence.
    """

    if len(tasks) != len(deltas):
        raise ValueError("tasks and deltas must be the same length")
    grouped: dict[str, list[float]] = {}
    for task, delta in zip(tasks, deltas, strict=True):
        grouped.setdefault(cluster_key(str(task)), []).append(float(delta))
    return [sum(v) / len(v) for _, v in sorted(grouped.items())]


def cluster_bootstrap(
    per_task_deltas: Sequence[float],
    *,
    tasks: Sequence[str] | None = None,
    iterations: int = 10_000,
    confidence: float = 0.95,
    seed: int = 12345,
) -> tuple[float, float] | None:
    """Percentile interval on the mean per-task delta, resampling TASKS.

    THE single implementation. `scripts/analyze_pilot.py` carried a second one with a different
    seed (42 against 12345) and a different index clamp, and it computed every published headline
    interval, so the repository had two answers to "what is the CI" and no test that they agreed.

    ⚠️ **This interval does not include run-to-run variance, and the two published replications
    measure how much that omits.** `pilot-003-deepseek` and `pilot-004-placebo` ran the same
    protocol, model, tasks and seeds; their per-task recall-minus-claude_md deltas correlate at
    r = 0.625, the mean absolute difference is 0.146, and 5 of 24 tasks flip sign or move by at
    least 0.50. Resampling tasks within one run treats each task's delta as measured without error.
    It is not. Quote this interval with that stated, or report both runs.

    Pass ``tasks`` to collapse convention-sharing tasks into one unit first, per
    ``CONVENTION_CLUSTERS``. Without it every task counts once, which is right only when no two
    of them encode the same convention.
    """

    if tasks is not None:
        keep = [
            (str(t), float(d))
            for t, d in zip(tasks, per_task_deltas, strict=True)
            if d is not None and math.isfinite(float(d))
        ]
        per_task_deltas = collapse_to_clusters([t for t, _ in keep], [d for _, d in keep])

    usable = [float(d) for d in per_task_deltas if d is not None and math.isfinite(float(d))]
    if len(usable) < 2 or len(set(usable)) == 1:
        return None
    rng = random.Random(seed)
    size = len(usable)
    means = sorted(
        sum(usable[rng.randrange(size)] for _ in range(size)) / size for _ in range(iterations)
    )
    lo_q = (1.0 - confidence) / 2.0
    lo = means[min(len(means) - 1, int(lo_q * len(means)))]
    hi = means[min(len(means) - 1, int((1.0 - lo_q) * len(means)))]
    return (lo, hi)


def effect_concentration(per_task_deltas: Mapping[str, float]) -> dict[str, Any]:
    """How much of a headline delta comes from how few tasks.

    A mean over 24 tasks reads as a broad improvement. Measured on `pilot-004-placebo`, 9 of 24
    tasks contributed a nonzero recall-minus-claude_md delta and the top three carried 64% of the
    total; on `pilot-003-deepseek`, 11 of 24 and 38%. Both are real results and neither is "the
    memory layer helps across the board", so the counts belong beside the mean rather than in a
    reader's head.
    """

    deltas = {task: float(value) for task, value in per_task_deltas.items()}
    if not deltas:
        return {"n_tasks": 0}
    nonzero = {t: d for t, d in deltas.items() if abs(d) > 1e-12}
    positive = sorted((d for d in deltas.values() if d > 0), reverse=True)
    total_positive = sum(positive)
    return {
        "n_tasks": len(deltas),
        "n_contributing": len(nonzero),
        "n_zero": len(deltas) - len(nonzero),
        "n_helped": sum(1 for d in deltas.values() if d > 0),
        "n_hurt": sum(1 for d in deltas.values() if d < 0),
        "top3_share_of_positive": (
            round(sum(positive[:3]) / total_positive, 3) if total_positive else None
        ),
        "largest_contributors": [
            task for task, _ in sorted(nonzero.items(), key=lambda kv: -abs(kv[1]))[:3]
        ],
    }


def summarize_by_task(
    pairs_by_task: dict[str, Sequence[tuple[bool, bool]]],
    *,
    n: int = 10000,
    confidence: float = 0.95,
    seed: int = 12345,
) -> dict[str, Any]:
    """The per-TASK view, which is the conservative reading of a repeated-measures design.

    Repetitions of one task are **not** independent: the same prompt, the same corpus and the same
    governing memo produce correlated outcomes, so treating 10 repetitions of 4 traps as 40
    independent pairs overstates confidence. This collapses each trap to one rate per arm, so the
    unit of evidence is the hazard rather than the session.

    ⚠️ **With few traps this view cannot reach significance at any effect size, and that is a
    property of the design rather than a result.** A sign test over 4 tasks bottoms out at p=0.125
    even when all four move the same way. So `n_improved` and the per-task deltas are reported as
    DESCRIPTIVE, and no p-value is invented for them. The cluster bootstrap resamples whole tasks,
    which is the honest interval for generalising to a new hazard, and it will be wide.
    """

    rates = [
        TaskRate(
            task=task,
            n_reps=len(pairs),
            on_rate=sum(1 for on, _ in pairs if on) / len(pairs),
            off_rate=sum(1 for _, off in pairs if off) / len(pairs),
        )
        for task, pairs in sorted(pairs_by_task.items())
        if pairs
    ]
    if not rates:
        return {"tasks": [], "n_tasks": 0, "note": "no tasks"}

    deltas = [r.delta for r in rates]
    improved = sum(1 for d in deltas if d < 0)
    worsened = sum(1 for d in deltas if d > 0)

    # 🔁 This carried its OWN copy of the bootstrap until 2026-08-30, while cluster_bootstrap's
    # docstring described itself as "THE single implementation". It was not: this copy computed
    # every `cluster_ci` the harm suite publishes, so the shared function and the reported number
    # came from different code. That is exactly the condition that docstring was written about,
    # reintroduced one function below it.
    clusters = collapse_to_clusters([r.task for r in rates], deltas)
    cluster_ci = cluster_bootstrap(
        deltas,
        tasks=[r.task for r in rates],
        iterations=n,
        confidence=confidence,
        seed=seed,
    )

    return {
        "tasks": [r.to_dict() for r in rates],
        "n_tasks": len(rates),
        # The resampling unit, which is smaller than n_tasks whenever two tasks share a
        # convention. Published so a reader can see the collapse rather than infer it.
        "n_clusters": len(clusters),
        "mean_delta": sum(deltas) / len(deltas),
        "improved": improved,
        "worsened": worsened,
        "unchanged": len(deltas) - improved - worsened,
        # Resamples TASKS, not pairs, so the interval answers "what would a new hazard do".
        "cluster_ci": list(cluster_ci) if cluster_ci else None,
        "note": (
            f"descriptive: {len(rates)} distinct traps. A sign test over this many cannot reach "
            f"p<0.05 at any effect size, so no p-value is reported for this view."
        ),
    }


def compare_binary(metric: str, pairs: Sequence[tuple[bool, bool]]) -> PairedResult:
    """Compare a paired binary endpoint, such as whether a trap was triggered."""

    on = [bool(a) for a, _ in pairs]
    off = [bool(b) for _, b in pairs]
    n = len(pairs)
    if n < MIN_PAIRS:
        return PairedResult(
            metric=metric, n_pairs=n, on_mean=_mean([float(x) for x in on]),
            off_mean=_mean([float(x) for x in off]), delta_mean=None, delta_median=None,
            delta_ci=None,
            p_value=None, test="mcnemar_exact",
            note=f"only {n} pairs; below {MIN_PAIRS} no split of the discordant pairs can reach "
                 f"p < 0.05, so a p-value here would describe the sample size, not the effect",
        )
    p, b, c = mcnemar_exact(on, off)
    deltas = [float(x) - float(y) for x, y in zip(on, off)]
    note = f"discordant pairs: on-only={b}, off-only={c}"
    if p is None:
        note += "; every pair agreed, so the test is undefined"
    return PairedResult(
        metric=metric, n_pairs=n, on_mean=_mean([float(x) for x in on]),
        off_mean=_mean([float(x) for x in off]), delta_mean=_mean(deltas),
        delta_median=statistics.median(deltas) if deltas else None,
        delta_ci=paired_bootstrap(deltas), p_value=p, test="mcnemar_exact", note=note,
    )


def compare_continuous(metric: str, pairs: Sequence[tuple[float, float]]) -> PairedResult:
    """Compare a paired continuous endpoint, such as input tokens or wall time."""

    usable = [
        (float(a), float(b))
        for a, b in pairs
        # A missing measurement stays missing. Substituting zero would report an unmeasured
        # session as a free one, which is the schema's standing rule and matters most here,
        # where the whole endpoint is a cost.
        if a is not None and b is not None and math.isfinite(float(a)) and math.isfinite(float(b))
    ]
    n = len(usable)
    dropped = len(pairs) - n
    note = f"{dropped} pair(s) dropped for a missing measurement" if dropped else ""
    if n < MIN_PAIRS:
        return PairedResult(
            metric=metric, n_pairs=n, on_mean=_mean([a for a, _ in usable]),
            off_mean=_mean([b for _, b in usable]), delta_mean=None, delta_median=None,
            delta_ci=None,
            p_value=None, test="wilcoxon_signed_rank",
            note=(note + "; " if note else "") + f"only {n} usable pairs, below {MIN_PAIRS}",
        )
    deltas = [a - b for a, b in usable]
    return PairedResult(
        metric=metric, n_pairs=n, on_mean=_mean([a for a, _ in usable]),
        off_mean=_mean([b for _, b in usable]), delta_mean=_mean(deltas),
        delta_median=statistics.median(deltas) if deltas else None,
        delta_ci=paired_bootstrap(deltas), p_value=wilcoxon_signed_rank(deltas),
        test="wilcoxon_signed_rank", note=note,
    )
