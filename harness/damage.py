"""Separating "failed" from "failed BECAUSE it acted on retrieved evidence that was wrong".

Every task in this benchmark places its governing fact IN the corpus, so the suite can only ask
whether memory helps. It has no way to express harm, and a layer that helps 20% of cells while
harming 15% reports the same "+5 points" as one that helps 20% and harms 2%. Preregistration 005
adds corpus conditions where the evidence is absent, stale, contradictory or inapplicable; this
module is the part that makes their primary endpoint measurable.

The existing checker answers one question, pass or fail. That is not enough here, because two very
different things both read as "fail":

* the agent did not know the governing fact and produced a competent wrong answer, which is exactly
  what the `naive` reference does and is NOT evidence that memory hurt anything;
* the agent retrieved a planted, wrong fact and applied it, which IS.

A damage detector is a second, independent predicate over the finished sandbox, asking only the
second question. It never sees the checker's verdict, and the checker never sees its.

## The attribution constraint, learned while writing the first one

A planted wrong fact is only measurable if applying it produces an outcome **distinguishable from
the factless solution**. On `ts-base36-id`, an "adjacent" plant claiming another id scheme uses
full base36 would make the agent emit `ORD-24GI`, byte-identical to what the `naive` reference
produces with no memory at all. The cell would be damaged and unattributable. So a plant must bite
somewhere the factless answer does not, and every detector has to prove that by passing the
three-way gate in `tests/test_damage_detection.py`.

## Why a contradiction is raised rather than resolved

If the checker passes and the detector also fires, the deliverable is simultaneously correct and
built on the wrong fact. That is not a cell to score, it is two predicates disagreeing, and one of
them is wrong. Silently preferring either would bury a broken detector inside a published rate.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

#: The corpus conditions from preregistration 005. A detector is asked about one of these, because
#: the planted wrong fact differs per condition even for the same task.
CONDITIONS = ("absent", "superseded", "contradictory", "adjacent")


class Outcome(enum.Enum):
    """What one finished cell actually shows, in the three-way form damage requires."""

    SOLVED = "solved"
    #: Wrong, but not traceably because of retrieved evidence. The `naive` reference lands here.
    NEUTRAL_FAILURE = "neutral_failure"
    #: Wrong, and the deliverable embodies the planted wrong fact.
    DAMAGED = "damaged"


class ContradictoryVerdicts(RuntimeError):
    """The checker passed while the damage detector fired. One of them is wrong."""


@runtime_checkable
class DamageDetector(Protocol):
    def __call__(
        self, workdir: Path, oracle_dir: Path, condition: str
    ) -> tuple[bool, str]:  # pragma: no cover - structural
        """Return whether the deliverable embodies this condition's planted wrong fact."""


def classify(checker_ok: bool, damage_hit: bool, *, detail: str = "") -> Outcome:
    """Fold a checker verdict and a damage verdict into one outcome.

    Raises rather than choosing when the two disagree in the impossible direction.
    """

    if checker_ok and damage_hit:
        raise ContradictoryVerdicts(
            "the checker passed and the damage detector fired on the same sandbox: the "
            f"deliverable cannot be both correct and built on the planted wrong fact. {detail}"
        )
    if checker_ok:
        return Outcome.SOLVED
    return Outcome.DAMAGED if damage_hit else Outcome.NEUTRAL_FAILURE


def load_detector(task_dir: str | Path) -> Callable[..., tuple[bool, str]] | None:
    """Load ``<task_dir>/damage.py::detect``, or None for a task with no planted conditions."""

    path = Path(task_dir) / "damage.py"
    if not path.is_file():
        return None
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"damage_{Path(task_dir).name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load a damage detector from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Two different defects, and conflating them hides which one a task author made.
    if not hasattr(module, "detect"):
        raise AttributeError(f"{path} defines no `detect`")
    detect = module.detect
    if not callable(detect):
        raise TypeError(f"{path} defines `detect` but it is not callable")
    return detect


def detect_damage(
    task_dir: str | Path, workdir: Path, oracle_dir: Path, condition: str
) -> tuple[bool, str]:
    """Run one task's damage detector, or report that it has none."""

    if condition not in CONDITIONS:
        raise ValueError(f"unknown corpus condition {condition!r}; expected one of {CONDITIONS}")
    detect = load_detector(task_dir)
    if detect is None:
        return False, "no damage detector for this task"
    hit, reason = detect(Path(workdir), Path(oracle_dir), condition)
    return bool(hit), str(reason)


def outcome_for(
    task_dir: str | Path,
    workdir: Path,
    oracle_dir: Path,
    condition: str,
    checker_ok: bool,
    checker_verdict: str = "",
) -> tuple[Outcome, str]:
    """The full three-way classification for one finished cell."""

    hit, reason = detect_damage(task_dir, workdir, oracle_dir, condition)
    outcome = classify(checker_ok, hit, detail=f"checker said {checker_verdict!r}; detector said {reason!r}")
    return outcome, reason if hit else checker_verdict


def net_harm(paired: list[tuple[bool, bool]]) -> dict[str, Any]:
    """Net harm of an arm against `bare`, over paired cells of ``(arm_ok, bare_ok)``.

    This is the primary endpoint of preregistration 005, and it is a rate over ADMITTED PAIRED
    CELLS. Success rate cannot express harm: an arm that fixes as many cells as it breaks looks
    identical to one that touches nothing.
    """

    if not paired:
        raise ValueError("net harm needs at least one paired cell; a rate needs a denominator")
    harmed = sum(1 for arm_ok, bare_ok in paired if bare_ok and not arm_ok)
    helped = sum(1 for arm_ok, bare_ok in paired if arm_ok and not bare_ok)
    n = len(paired)
    return {
        "n_paired_cells": n,
        "harmed": harmed,
        "helped": helped,
        "damage_rate": harmed / n,
        "benefit_rate": helped / n,
        "net_harm": (harmed - helped) / n,
    }
