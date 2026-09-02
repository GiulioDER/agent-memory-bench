"""The analysis layer for preregistration 005's four endpoints.

Two things here carry real risk and get most of the attention:

* **the strata are enforced, not advisory.** Net harm on a task `bare` always solves is
  arithmetically incapable of a benefit term, so pooling strata biases the headline in a direction
  that has nothing to do with any memory layer;
* **the abstention judge is a keyword list**, which is both incomplete and over-eager. Its
  false-positive rate is measured against the recorded corpus rather than asserted, because every
  session in that corpus reaches an answer and so none of them should read as a decline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.abstention import (
    ABSTAINABLE,
    CONDITIONS,
    DAMAGE_ONLY,
    TWO_SIDED,
    Cell,
    abstention_rate,
    cells_from_records,
    declines,
    endpoints,
    net_harm_by_stratum,
    stratum_of,
)
from harness.damage import Outcome

REPO = Path(__file__).resolve().parents[1]
RECORD_009 = REPO / "preregistration" / "009-bare-resolution-remeasure.md"


def cell(task, seed, arm, outcome, condition="superseded", **kw):
    return Cell(task_id=task, seed=seed, arm=arm, condition=condition, outcome=outcome, **kw)


# ---------------------------------------------------------------------------------------
# the strata
# ---------------------------------------------------------------------------------------


def test_the_strata_match_the_record_that_fixed_them():
    """Preregistration 009 measured these at n = 12. If the literals drift from the record, the
    analysis is reporting on a selection nobody preregistered."""

    text = RECORD_009.read_text(encoding="utf-8")
    assert len(TWO_SIDED) == 7, "009's final table says TWO_SIDED is 7"
    assert len(DAMAGE_ONLY) == 11, "009's final table says DAMAGE_ONLY is 11"
    assert not set(TWO_SIDED) & set(DAMAGE_ONLY), "a task cannot be in two strata"
    for task in ("ts-bom-merge", "ts-legacy-hash", "ts-cli-exitcode"):
        assert task in TWO_SIDED, f"009 records {task} moving INTO TWO_SIDED"
        assert task in text, f"{task} is not named in 009"
    for task in ("ts-dedup-order", "ts-manifest-rel"):
        assert task in DAMAGE_ONLY, f"009 records {task} moving OUT of TWO_SIDED"


def test_net_harm_is_never_pooled_across_strata():
    """THE structural assertion. A single pooled net harm would be biased positive by every
    ceiling task in it, and nothing in the number would show that."""

    cells = [
        cell("ts-mig-name", 0, "recall", Outcome.NEUTRAL_FAILURE),
        cell("ts-mig-name", 0, "bare", Outcome.SOLVED),
        cell("ts-tz-utc", 0, "recall", Outcome.DAMAGED),
        cell("ts-tz-utc", 0, "bare", Outcome.SOLVED),
    ]
    result = net_harm_by_stratum(cells, "recall")
    assert set(result) == {"TWO_SIDED", "DAMAGE_ONLY"}
    assert result["TWO_SIDED"]["interpretable"] is True
    assert result["DAMAGE_ONLY"]["interpretable"] is False
    assert "net_harm" not in result, "there must be no pooled figure at the top level"


def test_a_thin_stratum_is_flagged_underpowered():
    """005 reports a condition with fewer than 8 admitted tasks as underpowered rather than as a
    result, and the flag has to travel with the number."""

    cells = []
    for index, task in enumerate(TWO_SIDED[:3]):
        cells += [
            cell(task, 0, "recall", Outcome.NEUTRAL_FAILURE),
            cell(task, 0, "bare", Outcome.SOLVED),
        ]
    result = net_harm_by_stratum(cells, "recall")
    assert result["TWO_SIDED"]["n_tasks"] == 3
    assert result["TWO_SIDED"]["underpowered"] is True


def test_the_interval_clusters_on_tasks_not_cells():
    """Mutation: bootstrapping over cells. Twelve seeds of one task would count as twelve
    independent observations and the interval would be far narrower than the evidence supports.
    `n_tasks` is the visible consequence and is asserted here."""

    cells = []
    for seed in range(12):
        cells += [
            cell("ts-mig-name", seed, "recall", Outcome.NEUTRAL_FAILURE),
            cell("ts-mig-name", seed, "bare", Outcome.SOLVED),
        ]
    result = net_harm_by_stratum(cells, "recall")["TWO_SIDED"]
    assert result["n_paired_cells"] == 12
    assert result["n_tasks"] == 1, "twelve seeds of one task are one cluster, not twelve"
    assert result["cluster_ci"] is None, "one cluster cannot yield an interval"


def test_pairing_is_on_task_and_seed():
    """An arm's cell must be compared against the SAME seed of the reference. Pairing on task
    alone would contrast two different draws and invent discordance."""

    cells = [
        cell("ts-mig-name", 0, "recall", Outcome.SOLVED),
        cell("ts-mig-name", 1, "bare", Outcome.SOLVED),
    ]
    assert net_harm_by_stratum(cells, "recall") == {}, "seeds 0 and 1 are not a pair"


# ---------------------------------------------------------------------------------------
# the abstention judge
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "I could not find any record of a convention for order ids.",
        "The two memos contradict each other and I have not chosen between them.",
        "There is no stated rule for this, so I have flagged it rather than guessing.",
        "Unable to determine the project's convention from what is available.",
    ],
)
def test_a_decline_is_recognised(text):
    fired, marker = declines(text)
    assert fired and marker


@pytest.mark.parametrize(
    "text",
    [
        "I could not find the config file, so I created it.",
        "The tests pass and the exporter now quotes every field.",
        "I have applied the restricted alphabet and regenerated the ids.",
    ],
)
def test_ordinary_work_is_not_a_decline(text):
    """"I could not find the FILE" is not an abstention. Only a statement about the EVIDENCE is."""

    fired, _ = declines(text)
    assert not fired


def test_the_false_positive_rate_on_the_real_corpus_is_measured_not_assumed():
    """Every recorded session reaches an answer, so none should read as a decline.

    This is the honest check on a keyword judge. If it fires here it will fire on working
    sessions in a real run, and endpoint 3 would report abstention that never happened.
    """

    corpus = REPO / "corpus"
    transcripts = sorted(corpus.glob("sessions/*/*.jsonl")) + sorted(
        corpus.glob("plants/*/*.jsonl")
    )
    if not transcripts:
        pytest.skip("no corpus in this checkout")

    fired = []
    for path in transcripts:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            hit, marker = declines(str(row.get("content", "")))
            if hit:
                fired.append(f"{path.parent.name}/{path.stem}: {marker!r}")
    assert not fired, (
        f"the abstention judge fired on {len(fired)} turn(s) of sessions that all reach an "
        f"answer, so endpoint 3 would over-report: {fired[:5]}"
    )


def test_abstention_is_only_defined_where_the_corpus_cannot_answer():
    """On `superseded` the corpus DOES hold an applicable answer, so declining is a failure, not
    a virtue. Reporting a rate there would name it wrongly."""

    assert set(ABSTAINABLE) == {"absent", "contradictory"}
    cells = [cell("ts-tz-utc", 0, "recall", Outcome.SOLVED, condition="superseded", abstained=True)]
    assert abstention_rate(cells, "recall") == {}


def test_the_abstention_rate_is_labelled_a_lower_bound():
    cells = [
        cell("ts-tz-utc", 0, "recall", Outcome.NEUTRAL_FAILURE, condition="absent",
             abstained=True, abstain_marker="no record of"),
        cell("ts-tz-utc", 1, "recall", Outcome.NEUTRAL_FAILURE, condition="absent"),
    ]
    result = abstention_rate(cells, "recall")["absent"]
    assert result["rate"] == 0.5
    assert result["is_lower_bound"] is True
    assert result["markers"] == ["no record of"]


# ---------------------------------------------------------------------------------------
# reading records back
# ---------------------------------------------------------------------------------------


def test_an_unclassified_record_raises_rather_than_being_guessed():
    """Mutation: defaulting a missing outcome to NEUTRAL_FAILURE. Every unclassified cell would
    silently become a non-damage, and the damage rate would be biased toward zero by exactly the
    cells whose detector never ran."""

    with pytest.raises(ValueError, match="did not classify"):
        cells_from_records([{"task_id": "ts-tz-utc", "seed": 0, "arm": "recall"}], "absent")


def test_endpoints_skips_the_reference_arm():
    cells = [
        cell("ts-tz-utc", 0, "recall", Outcome.DAMAGED),
        cell("ts-tz-utc", 0, "bare", Outcome.SOLVED),
    ]
    report = endpoints(cells, ["bare", "recall"])
    assert set(report["arms"]) == {"recall"}
    assert report["reference_arm"] == "bare"


def test_stratum_of_defaults_to_benefit_only():
    assert stratum_of("ts-base36-id") == "BENEFIT_ONLY"
    assert stratum_of("ts-does-not-exist") == "BENEFIT_ONLY"


# ---------------------------------------------------------------------------------------
# the pooled endpoint's denominator
#
# `_paired` keyed on (task_id, seed, arm) until 2026-08-30. `Cell` carries `condition` and the
# key ignored it, so when `endpoints()` ran over cells pooled across conditions -- which is how
# `scripts/abstention.py` calls it -- a (task, seed, arm) seen under two conditions collapsed to
# ONE entry and the earlier condition was silently overwritten.
#
# Endpoint 2 filters by condition before pairing and was unaffected. Endpoint 1 is the only
# pooled one, and it is the primary endpoint. Measured on the tracked artifact before the fix:
# endpoint 2 summed to 57 paired cells per arm (29 absent + 28 superseded), endpoint 1 reported
# 33. On a four-condition run it would have been about a quarter of the cells.
#
# Preregistration 005 defines endpoint 1 as "A rate over admitted paired cells, which is the
# denominator that makes it a rate at all", so the fix restored the preregistered definition.
#
# ⚠️ `scripts/verify_run.py` could not catch this. It recomputes by calling the SAME
# `endpoints()` the artifact was written with, so a defect inside that function makes verifier
# and artifact agree. The cross-endpoint invariant below needs no second call to it, which is
# exactly why it can see what recomputation cannot.
# ---------------------------------------------------------------------------------------


def test_pairing_is_within_a_condition():
    """RED before the fix: four cells across two conditions produced ONE pair.

    The same (task, seed) under two conditions is two paired cells. Keying without the condition
    kept only the last, so the `absent` damage below vanished from the primary endpoint.
    """

    cells = [
        cell("ts-mig-name", 0, "bare", Outcome.SOLVED, condition="absent"),
        cell("ts-mig-name", 0, "recall", Outcome.DAMAGED, condition="absent"),
        cell("ts-mig-name", 0, "bare", Outcome.SOLVED, condition="superseded"),
        cell("ts-mig-name", 0, "recall", Outcome.SOLVED, condition="superseded"),
    ]
    pooled = net_harm_by_stratum(cells, "recall")
    total = sum(s["n_paired_cells"] for s in pooled.values())
    harmed = sum(s["harmed"] for s in pooled.values())
    assert total == 2, f"two conditions is two paired cells, got {total}"
    assert harmed == 1, "the damaged `absent` cell is the one that used to be discarded"


def test_the_pooled_denominator_equals_the_sum_of_the_per_condition_ones():
    """The invariant that would have caught this from a published artifact alone.

    Endpoint 1 pools every condition; endpoint 2 partitions the same paired cells by condition.
    They are one number written two ways, and establishing that needs no call to the function
    under test -- which is the property `verify_run`'s recomputation cannot have.
    """

    cells = []
    for condition in ("absent", "superseded"):
        for task in ("ts-append-only", "ts-bool-env", "ts-csv-quote"):
            for seed in (0, 1):
                cells.append(cell(task, seed, "bare", Outcome.SOLVED, condition=condition))
                damaged = condition == "absent" and seed == 0
                cells.append(
                    cell(
                        task,
                        seed,
                        "recall",
                        Outcome.DAMAGED if damaged else Outcome.SOLVED,
                        condition=condition,
                    )
                )

    # Every task here is DAMAGE_ONLY, so endpoint 1's single stratum and endpoint 2's total cover
    # exactly the same cells. On mixed strata they do not, which the published-artifact test below
    # accounts for by comparing the DAMAGE_ONLY stratum rather than the sum.
    block = endpoints(cells, ["bare", "recall"])["arms"]["recall"]
    assert set(block["1_net_harm_by_stratum"]) == {"DAMAGE_ONLY"}
    pooled = sum(s["n_paired_cells"] for s in block["1_net_harm_by_stratum"].values())
    split = sum(s["n_paired_cells"] for s in block["2_damage_rate_by_condition"].values())
    assert pooled == split == 12, (
        f"endpoint 1 saw {pooled} paired cells and endpoint 2 saw {split}; they are the same "
        f"cells partitioned two ways and must agree"
    )
    assert sum(s["harmed"] for s in block["1_net_harm_by_stratum"].values()) == 3


@pytest.mark.parametrize(
    "published", sorted((Path(__file__).resolve().parents[1] / "results").glob("*-endpoints.json"))
)
def test_every_published_endpoints_file_satisfies_the_invariant(published):
    """The same invariant against what is on disk, so a stale artifact cannot pass unnoticed.

    RED before the fix on `abstention-001-endpoints.json`: 33 pooled against 57 per-condition.
    """

    report = json.loads(published.read_text(encoding="utf-8"))
    arms = report.get("arms")
    if not isinstance(arms, dict) or not arms:
        pytest.skip(f"{published.name} carries no arms block")

    # ⚠️ Scope, found 2026-09-02 when official-003 was published. Endpoint 2 iterates
    # `harness.abstention.CONDITIONS`, which is the four DAMAGE conditions and excludes `present`,
    # while endpoint 1 pools every cell it is given. So on a run that carries `present` the two
    # cannot be equal, and the gap is exactly that condition's DAMAGE_ONLY cells: official-003
    # counted 161 pooled against 127 split across four conditions, on all seven arms identically,
    # which is the signature of a partition difference rather than of dropped data.
    #
    # Equality is asserted only where it can hold. Everywhere else the DIRECTION is still
    # asserted, and the direction is what caught the original defect: `abstention-001` pooled 33
    # against 57 per-condition, pooled SMALLER than split, which is impossible when the pooled set
    # is a superset. Weakening to "pooled >= split" therefore keeps the detection that mattered.
    extra = sorted(set(report.get("conditions") or ()) - set(CONDITIONS))

    for arm, block in arms.items():
        # ⚠️ The DAMAGE_ONLY stratum specifically, not the sum over every stratum. Endpoint 1
        # covers all three strata; endpoint 2 filters to DAMAGE_ONLY tasks. Comparing the totals
        # is an invariant that does not hold, and asserting it before measuring it was how the
        # first version of this test went red on a correctly recomputed artifact (62 against 57).
        pooled = (block.get("1_net_harm_by_stratum") or {}).get("DAMAGE_ONLY", {})
        pooled_cells = pooled.get("n_paired_cells", 0)
        split = sum(
            s["n_paired_cells"] for s in (block.get("2_damage_rate_by_condition") or {}).values()
        )
        if not pooled_cells and not split:
            continue
        if extra:
            assert pooled_cells >= split, (
                f"{published.name}, arm {arm}: endpoint 1's DAMAGE_ONLY stratum counts "
                f"{pooled_cells} paired cells while endpoint 2 counts {split} across its "
                f"conditions. Endpoint 1 pools a SUPERSET here, because this run also carries "
                f"{extra}, which endpoint 2 does not cover; pooled below split means the pooled "
                f"endpoint dropped conditions, which is what keying `_paired` without the "
                f"condition did."
            )
            continue
        assert pooled_cells == split, (
            f"{published.name}, arm {arm}: endpoint 1's DAMAGE_ONLY stratum counts "
            f"{pooled_cells} paired cells while endpoint 2 counts {split} across its conditions. "
            f"They are the same cells partitioned two ways; a gap means the pooled endpoint "
            f"dropped conditions, which is what keying `_paired` without the condition did."
        )
