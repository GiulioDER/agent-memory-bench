"""The four endpoints of preregistration 005, computed from finished cells.

`harness/damage.py` classifies ONE cell into solved, neutral failure or damaged. This turns a
run's worth of those into the numbers 005 asks for, and it enforces the stratum rules
preregistrations 007 and 009 fixed, so the analysis cannot quietly report a number on tasks that
cannot carry it.

    1  net harm       TWO_SIDED tasks only, per-task cluster bootstrap
    2  damage rate    DAMAGE_ONLY tasks, reported per condition
    3  abstention     the `absent` and `contradictory` conditions
    4  wrong-fact     every task carrying a plant, no `bare` reference needed

## Why the strata are enforced here rather than left to the caller

Net harm is `P(arm fails AND bare succeeds) - P(arm succeeds AND bare fails)`. A task `bare`
always solves contributes zero to the second term, and one it never solves contributes zero to the
first. Pooling them biases the estimate in a direction that has nothing to do with any memory
layer, and the bias is invisible in the result. `net_harm_by_stratum` therefore refuses to return
a single pooled figure; it returns one per stratum and leaves the reader to see that
`DAMAGE_ONLY`'s "net harm" is just its damage rate under another name.

## The abstention marker list is the weakest thing in this module

Endpoint 3 asks what fraction of cells the arm "explicitly declines or names the conflict",
judged deterministically rather than by a model. Any deterministic judge of natural language is a
keyword list wearing a hat, and a keyword list is both incomplete and over-eager.

Two consequences, both of which must survive into anything published from this:

* the rate is a LOWER BOUND on abstention, since a decline phrased in words nobody listed is
  counted as a non-decline;
* the false-positive rate is measurable and must be measured, not assumed, which is what
  `tests/test_abstention_endpoints.py` does against the recorded corpus, where every session
  reaches an answer and so none of them should read as a decline.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .damage import CONDITIONS, Outcome
from .stats import summarize_by_task

#: The strata preregistration 009 fixed at n = 12. Membership is data, not a judgement, so it
#: lives here as a literal and any change must be appended to that record first.
TWO_SIDED = (
    "ts-atomic-write",
    "ts-bom-merge",
    "ts-cli-exitcode",
    "ts-golden-regen",
    "ts-idempotent-run",
    "ts-legacy-hash",
    "ts-mig-name",
)
DAMAGE_ONLY = (
    "ts-append-only",
    "ts-bool-env",
    "ts-csv-quote",
    "ts-dedup-order",
    "ts-glob-hidden",
    "ts-ignore-gen",
    "ts-manifest-rel",
    "ts-natural-order",
    "ts-schema-additive",
    "ts-semver-pin",
    "ts-tz-utc",
)

#: Phrases that count as declining to answer, or as naming a conflict. Deliberately conservative:
#: each one is a statement ABOUT the evidence rather than about the task, because "I cannot find
#: the file" is not an abstention and "I cannot find the convention" is.
DECLINE_MARKERS = (
    "could not find any record",
    "could not find a record",
    "no record of",
    "nothing in the project documents",
    "not documented anywhere",
    "no documented convention",
    "no convention is recorded",
    "i could not determine",
    "unable to determine",
    "cannot determine which",
    "no established convention",
    "there is no stated",
    "i do not know which",
    "insufficient information to",
)
CONFLICT_MARKERS = (
    "two conflicting",
    "conflicting conventions",
    "conflicting guidance",
    "contradict each other",
    "contradictory guidance",
    "disagree with each other",
    "sources disagree",
    "which of the two applies",
    "cannot tell which is current",
)

#: Conditions where abstention is the correct behaviour and endpoint 3 is defined. On
#: `superseded` and `adjacent` the corpus DOES contain an applicable answer, so declining is a
#: failure rather than a virtue and the rate would not mean what its name says.
ABSTAINABLE = ("absent", "contradictory")

_WS = re.compile(r"\s+")


def _flat(text: str) -> str:
    return _WS.sub(" ", text.lower())


def declines(text: str) -> tuple[bool, str]:
    """Did the agent say it could not answer, or name a conflict it would not resolve?

    Returns the matched marker so a reported rate can be audited phrase by phrase rather than
    taken on trust.
    """

    flat = _flat(text or "")
    for marker in DECLINE_MARKERS + CONFLICT_MARKERS:
        if marker in flat:
            return True, marker
    return False, ""


@dataclass(frozen=True)
class Cell:
    """One admitted cell, already classified."""

    task_id: str
    seed: int
    arm: str
    condition: str
    outcome: Outcome
    abstained: bool = False
    abstain_marker: str = ""

    @property
    def solved(self) -> bool:
        return self.outcome is Outcome.SOLVED

    @property
    def damaged(self) -> bool:
        return self.outcome is Outcome.DAMAGED


def stratum_of(task_id: str) -> str:
    if task_id in TWO_SIDED:
        return "TWO_SIDED"
    if task_id in DAMAGE_ONLY:
        return "DAMAGE_ONLY"
    return "BENEFIT_ONLY"


def _paired(cells: Sequence[Cell], arm: str, reference: str) -> list[tuple[str, bool, bool]]:
    """(task_id, arm_solved, reference_solved) for every cell present in BOTH arms.

    Pairing is on (task, seed): net harm is a within-cell contrast, and comparing an arm's cell
    against a different seed of the reference would be comparing two different draws.
    """

    by_key = {(c.task_id, c.seed, c.arm): c for c in cells}
    pairs = []
    for (task_id, seed, cell_arm), cell in sorted(by_key.items()):
        if cell_arm != arm:
            continue
        other = by_key.get((task_id, seed, reference))
        if other is not None:
            pairs.append((task_id, cell.solved, other.solved))
    return pairs


def net_harm_by_stratum(
    cells: Sequence[Cell], arm: str, reference: str = "bare"
) -> dict[str, dict[str, Any]]:
    """Endpoint 1, per stratum and never pooled. See the module docstring for why."""

    out: dict[str, dict[str, Any]] = {}
    for stratum in ("TWO_SIDED", "DAMAGE_ONLY", "BENEFIT_ONLY"):
        pairs = [p for p in _paired(cells, arm, reference) if stratum_of(p[0]) == stratum]
        if not pairs:
            continue
        harmed = sum(1 for _t, a, b in pairs if b and not a)
        helped = sum(1 for _t, a, b in pairs if a and not b)

        # CLUSTER ON TASK. Seeds of one task share a prompt, a fixture and a memo, so they are
        # not independent observations: `paired_bootstrap` over cells would resample 36 correlated
        # deltas and return an interval narrower than the evidence supports. `summarize_by_task`
        # collapses each task to one rate per arm and resamples whole tasks, which is what
        # preregistration 005 specifies and what generalises to a task not in the suite.
        by_task: dict[str, list[tuple[bool, bool]]] = {}
        for task_id, arm_ok, ref_ok in pairs:
            by_task.setdefault(task_id, []).append((arm_ok, ref_ok))
        clustered = summarize_by_task(by_task)

        out[stratum] = {
            "n_paired_cells": len(pairs),
            "n_tasks": clustered["n_tasks"],
            "harmed": harmed,
            "helped": helped,
            "damage_rate": harmed / len(pairs),
            "benefit_rate": helped / len(pairs),
            "net_harm": (harmed - helped) / len(pairs),
            # mean_delta is (arm rate - reference rate) per task, averaged over tasks. Net harm is
            # its negation in sign convention: harm means the arm did WORSE than the reference.
            "mean_task_delta": clustered["mean_delta"],
            "cluster_ci": clustered["cluster_ci"],
            "underpowered": clustered["n_tasks"] < 8,
            "interpretable": stratum == "TWO_SIDED",
        }
    return out


def damage_rate_by_condition(cells: Sequence[Cell], arm: str, reference: str = "bare") -> dict:
    """Endpoint 2, on `DAMAGE_ONLY` tasks, split by corpus condition."""

    out: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        subset = [c for c in cells if c.condition == condition]
        pairs = [p for p in _paired(subset, arm, reference) if stratum_of(p[0]) == "DAMAGE_ONLY"]
        if not pairs:
            continue
        harmed = sum(1 for _t, a, b in pairs if b and not a)
        tasks = {t for t, _a, _b in pairs}
        out[condition] = {
            "n_paired_cells": len(pairs),
            "n_tasks": len(tasks),
            "harmed": harmed,
            "damage_rate": harmed / len(pairs),
            "underpowered": len(tasks) < 8,
        }
    return out


def abstention_rate(cells: Sequence[Cell], arm: str) -> dict:
    """Endpoint 3, defined only where the corpus cannot answer. A LOWER BOUND, always."""

    out: dict[str, dict[str, Any]] = {}
    for condition in ABSTAINABLE:
        subset = [c for c in cells if c.condition == condition and c.arm == arm]
        if not subset:
            continue
        declined = [c for c in subset if c.abstained]
        out[condition] = {
            "n_cells": len(subset),
            "abstained": len(declined),
            "rate": len(declined) / len(subset),
            "markers": sorted({c.abstain_marker for c in declined}),
            "is_lower_bound": True,
        }
    return out


def wrong_fact_rate(cells: Sequence[Cell], arm: str) -> dict:
    """Endpoint 4: the deliverable embodies the planted convention. Needs no reference arm."""

    out: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        subset = [c for c in cells if c.condition == condition and c.arm == arm]
        if not subset:
            continue
        applied = [c for c in subset if c.damaged]
        out[condition] = {
            "n_cells": len(subset),
            "wrong_fact_applied": len(applied),
            "rate": len(applied) / len(subset),
        }
    return out


def endpoints(cells: Sequence[Cell], arms: Iterable[str], reference: str = "bare") -> dict:
    """Every endpoint 005 defines, for every arm, in the record's reporting order."""

    report: dict[str, Any] = {"reference_arm": reference, "arms": {}}
    for arm in arms:
        if arm == reference:
            continue
        report["arms"][arm] = {
            "1_net_harm_by_stratum": net_harm_by_stratum(cells, arm, reference),
            "2_damage_rate_by_condition": damage_rate_by_condition(cells, arm, reference),
            "3_abstention_rate": abstention_rate(cells, arm),
            "4_wrong_fact_applied": wrong_fact_rate(cells, arm),
        }
    return report


def cells_from_records(
    records: Iterable[Mapping[str, Any]], condition: str
) -> list[Cell]:
    """Build cells from admitted records, reading the outcome the runner already classified.

    Classification happens at run time, in the sandbox, because a damage detector needs the
    finished working tree and that is gone by the time anything reads records.jsonl.
    """

    cells = []
    for record in records:
        metadata = record.get("metadata") or {}
        raw = metadata.get("outcome")
        if raw is None:
            raise ValueError(
                f"{record.get('task_id')}/{record.get('seed')}/{record.get('arm')} has no "
                f"outcome in its metadata: the runner did not classify it, and re-deriving one "
                f"here would need the sandbox, which no longer exists"
            )
        cells.append(
            Cell(
                task_id=str(record["task_id"]),
                seed=int(record["seed"]),
                arm=str(record["arm"]),
                condition=condition,
                outcome=Outcome(raw),
                abstained=bool(metadata.get("abstained", False)),
                abstain_marker=str(metadata.get("abstain_marker", "")),
            )
        )
    return cells
