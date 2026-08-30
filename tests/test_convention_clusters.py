"""Tasks that encode one convention must be resampled as one unit.

`scripts/audit_corpus.py` flags convention-sharing task pairs and exits 0, so nothing enforces
acting on the warning. These tests are what enforces it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.stats import (
    CONVENTION_CLUSTERS,
    cluster_bootstrap,
    cluster_key,
    collapse_to_clusters,
    summarize_by_task,
)

PAIR = ("ts-golden-regen", "ts-ignore-gen")


def test_the_flagged_pair_is_actually_clustered():
    """Mutation: drop either task from CONVENTION_CLUSTERS.

    Both encode "do not hand-edit this generated file, run the script", applied to test goldens
    and to an ignore file. A product that misunderstands it fails both, so counting them twice
    overstates how many independent hazards agreed.
    """

    assert cluster_key(PAIR[0]) == cluster_key(PAIR[1]), (
        "the pair audit_corpus flags must share a resampling unit"
    )
    assert cluster_key("ts-tz-utc") == "ts-tz-utc", "an unrelated task is its own unit"


def test_collapsing_averages_within_a_cluster_and_keeps_everything_else():
    """Averaging, not discarding: every task's evidence stays in the estimate.

    What the collapse removes is the double weight in the RESAMPLING, which is the part that
    inflates confidence. Dropping one of the pair instead would throw away real measurements.
    """

    tasks = [PAIR[0], PAIR[1], "ts-tz-utc"]
    collapsed = sorted(collapse_to_clusters(tasks, [0.4, 0.2, -0.5]))

    assert len(collapsed) == 2, "the convention-sharing pair becomes one unit"
    assert collapsed[0] == pytest.approx(-0.5), "the unrelated task passes through untouched"
    assert collapsed[1] == pytest.approx(0.3), "the pair is averaged, not dropped"


def test_the_collapsed_interval_cannot_see_the_split_and_so_must_cross_the_uncollapsed_one():
    """⚠️ This asserts the OPPOSITE of what stood here, because what stood here was false.

    The previous test was `test_clustering_never_narrows_the_interval`, asserting
    `width(collapsed) >= width(loose)` on the single fixture `deltas = [0.4, 0.4, -0.2, 0.1]`.
    That gives the clustered pair IDENTICAL values, the one sub-region where averaging removes no
    dispersion and only the reduction in n operates, so widening is guaranteed by construction.
    It asserted a universal from the one point of it that holds, and it is the reason the false
    claim in `harness/stats.py` survived long enough to become the justification for the change.

    Hold the pair MEAN fixed and move the split. Measured on the shipped code with this fixture's
    own co-tasks:

        pair          uncollapsed   collapsed   narrows
        (+0.4, +0.4)     0.4500      0.6000       no
        (+0.6, +0.2)     0.5750      0.6000       no
        (+0.7, +0.1)     0.6750      0.6000      YES
        (+1.0, -0.2)     0.9000      0.6000      YES

    The mechanism, which is what this pins rather than any single verdict: the collapsed width is
    INVARIANT in the split, because averaging erases the pair's disagreement before the bootstrap
    ever sees it, while the uncollapsed width grows with that disagreement. Two lines, one flat
    and one rising, therefore cross. Where they cross depends on the co-tasks and is not asserted.
    """

    tasks = [PAIR[0], PAIR[1], "ts-tz-utc", "ts-semver-pin"]
    # Generated rather than listed, so "the pair mean is fixed" is structural instead of an
    # assertion about this function's own constant, which could not fail.
    splits = [(0.4 + i * 0.1, 0.4 - i * 0.1) for i in range(7)]

    widths = []
    for pair in splits:
        deltas = [pair[0], pair[1], -0.2, 0.1]
        loose = cluster_bootstrap(deltas)
        tight = cluster_bootstrap(deltas, tasks=tasks)
        assert loose and tight
        widths.append((loose[1] - loose[0], tight[1] - tight[0]))

    collapsed = {round(t, 6) for _l, t in widths}
    assert len(collapsed) == 1, (
        f"the collapsed width must not depend on the split, since the pair is averaged before "
        f"the bootstrap sees it; got {sorted(collapsed)}"
    )

    uncollapsed = [loose for loose, _t in widths]
    assert uncollapsed == sorted(uncollapsed), (
        f"the uncollapsed width must grow as the pair disagrees more; got {uncollapsed}"
    )

    assert widths[0][1] > widths[0][0], "the concordant split is the case that genuinely widens"
    assert widths[-1][1] < widths[-1][0], (
        "a fully discordant pair at the same mean must NARROW the interval, which is the claim "
        "`can only widen` denied"
    )


def test_a_discordant_cluster_can_manufacture_a_significant_result():
    """The consequence that sets the severity, and the reason this is not a documentation nit.

    Measured over the stated domain: 13 of 300 draws on a 3-seed grid (4.3%) turn an interval
    that includes zero into one that excludes it. A benchmark whose author's own product is under
    test cannot publish an interval that can acquire significance from a modelling choice.
    """

    # ⚠️ The first fixture here ([1.0, -1.0, 0.2, -0.2, 0.1, -0.1]) narrowed the interval but did
    # NOT flip it: the collapsed interval still contained zero, so the test's own headline was the
    # one thing it did not assert. These deltas are multiples of 1/3, i.e. what a 3-seed grid
    # actually produces, and were found by sweeping that lattice for a case that genuinely flips.
    tasks = [PAIR[0], PAIR[1], "ts-tz-utc", "ts-semver-pin", "ts-atomic-write", "ts-bom-merge"]
    deltas = [2 / 3, -2 / 3, -1 / 3, -1 / 3, -1 / 3, -2 / 3]

    loose = cluster_bootstrap(deltas)
    tight = cluster_bootstrap(deltas, tasks=tasks)
    assert loose and tight
    assert loose[0] <= 0 <= loose[1], (
        f"the uncollapsed interval must include zero for this test to mean anything; got {loose}"
    )
    assert not (tight[0] <= 0 <= tight[1]), (
        f"THE CLAIM: collapsing a discordant convention pair turns a null result into a "
        f"significant one. Uncollapsed {loose} includes zero; collapsed {tight} must not."
    )
    assert (tight[1] - tight[0]) < (loose[1] - loose[0])


def test_collapsing_can_destroy_the_interval_entirely():
    """When every collapsed unit is identical, `cluster_bootstrap` returns None.

    A published `cluster_ci: null` where an interval stood is a silent loss, not an error.
    """

    deltas = [1.0, -1.0, 0.0, 0.0]
    tasks = [PAIR[0], PAIR[1], "ts-tz-utc", "ts-semver-pin"]
    assert cluster_bootstrap(deltas) is not None
    assert cluster_bootstrap(deltas, tasks=tasks) is None


def test_the_source_no_longer_claims_the_collapse_only_widens():
    """Mutation guard: restoring the sentence must fail, because it is the load-bearing claim.

    It was offered as the reason the change was safe to make from a warning rather than from a
    measurement, so a reader who finds it will not re-derive the direction themselves.
    """

    import inspect
    import re

    import harness.stats as stats_module

    # Case-insensitive and on the semantic core, not one spelling: the first version grepped for
    # "can only WIDEN" and the same false claim in lowercase passed straight through it.
    source = inspect.getsource(stats_module)
    assert not re.search(r"only\s+(ever\s+)?widen", source, re.IGNORECASE), (
        "harness/stats.py claims collapsing can only widen the interval; it can narrow it, by up "
        "to 8.3x, and can turn a null result significant"
    )


def test_summarize_by_task_publishes_the_resampling_unit():
    """Mutation: drop `n_clusters` from the summary.

    A collapse a reader cannot see is a collapse they will not account for, and `n_tasks` alone
    reads as the number of independent units when it is not.
    """

    pairs = {
        PAIR[0]: [(True, False)] * 3,
        PAIR[1]: [(True, False)] * 3,
        "ts-tz-utc": [(False, True)] * 3,
    }
    out = summarize_by_task(pairs)
    assert out["n_tasks"] == 3
    assert out["n_clusters"] == 2, "the convention-sharing pair must count once"


def test_the_shared_bootstrap_is_the_only_one():
    """Mutation: reintroduce an inline bootstrap in summarize_by_task.

    It had one until 2026-08-30, while cluster_bootstrap's docstring called itself "THE single
    implementation". It was not: that copy computed every cluster_ci the harm suite publishes, so
    the shared function and the reported number came from different code. This asserts the
    condition that docstring describes actually holds.
    """

    source = (REPO / "harness" / "stats.py").read_text(encoding="utf-8")
    body = source[source.index("def summarize_by_task("):]
    body = body[: body.index("\ndef ", 1)]
    assert "random.Random(" not in body, (
        "summarize_by_task must call cluster_bootstrap, not carry its own resampling loop"
    )
    assert "cluster_bootstrap(" in body


def test_an_unclustered_task_is_unaffected():
    """Backward compatibility: without `tasks`, every delta counts once, exactly as before."""

    deltas = [0.1, -0.2, 0.3, 0.05]
    assert cluster_bootstrap(deltas) == cluster_bootstrap(deltas, tasks=list("abcd"))
    assert CONVENTION_CLUSTERS, "an empty cluster map would silently disable this whole file"
