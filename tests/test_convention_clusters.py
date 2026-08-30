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


def test_clustering_never_narrows_the_interval():
    """The asymmetry that makes this safe to do from a warning rather than a measurement.

    Being wrong about a cluster costs confidence. Being wrong the other way, treating correlated
    tasks as independent, costs correctness, and a published interval would be too tight.
    """

    tasks = [PAIR[0], PAIR[1], "ts-tz-utc", "ts-semver-pin"]
    deltas = [0.4, 0.4, -0.2, 0.1]

    loose = cluster_bootstrap(deltas)
    tight = cluster_bootstrap(deltas, tasks=tasks)
    assert loose and tight
    assert (tight[1] - tight[0]) >= (loose[1] - loose[0]), (
        "collapsing correlated tasks must not produce a narrower interval"
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
