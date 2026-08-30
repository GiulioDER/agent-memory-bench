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
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

#: The corpus conditions from preregistration 005. A detector is asked about one of these, because
#: the planted wrong fact differs per condition even for the same task.
#:
#: ⚠️ `present` is NOT one of them, and that is deliberate rather than an omission. Every
#: condition here varies how the evidence is BAD, so every one of them asks a detector "did the
#: arm apply a wrong fact". `present` has no plant and therefore no wrong fact to detect; asking
#: a damage detector about it is a category error. It is a condition of the CORPUS
#: (`ADVERSARIAL_CONDITIONS` plus `PRESENT` below) and not a condition of the damage machinery.
CONDITIONS = ("absent", "superseded", "contradictory", "adjacent")

#: The condition in which the governing fact is present, correct and unambiguous: the real
#: precursor session, no plant, nothing swapped. The identity transform on the corpus.
#:
#: It exists because without it this suite cannot reward a memory layer for being USEFUL.
#: `docs/reviews/2026-08-30-instrument-review.md` section 3: memory usefulness is a two-by-two,
#: and with only the four adversarial conditions above, one row of it cannot fire.
#:
#: | | corpus HAS the answer | corpus empty or misleading |
#: |---|---|---|
#: | product engages | win (benefit) | loss (damage) |
#: | product abstains | **missed** | win (correct refusal) |
#:
#: The "missed" cell is the one `present` instruments. Without it, never searching takes zero
#: damage and forfeits nothing, so abstinence is a strictly DOMINANT strategy and any ranking
#: drawn from this suite rewards the most conservative product rather than the most useful one.
#: That misrepresents every arm, including the third-party ones this project does not own.
PRESENT = "present"

#: Every condition a corpus can be assembled in. `CONDITIONS` stays the damage-detector's
#: vocabulary; this is the assembler's and the composite endpoint's.
CORPUS_CONDITIONS = (PRESENT, *CONDITIONS)

#: The four in which the corpus cannot answer correctly. Specificity is measured over these and
#: sensitivity over `PRESENT`; a composite needs both or it rewards a degenerate strategy.
ADVERSARIAL_CONDITIONS = CONDITIONS


class Outcome(enum.Enum):
    """What one finished cell actually shows, in the four-way form damage requires."""

    SOLVED = "solved"
    #: Wrong, and recognisably the factless answer: it matches what `naive` produces.
    NEUTRAL_FAILURE = "neutral_failure"
    #: Wrong, and the deliverable embodies the planted wrong fact.
    DAMAGED = "damaged"
    #: Wrong, and it matches NEITHER reference.
    #:
    #: This class was added on 2026-08-28 and it exists because its absence was one-directional.
    #: Every detector is an exact or structural matcher against a single hand-written damaged
    #: reference: `ts-tz-utc` requires the archive and remainder to equal the damaged split line for
    #: line, `ts-ignore-gen` requires the new rule first AND the rest byte-equal to the prior sorted
    #: content. An agent that retrieved the plant, applied it, and then slipped somewhere unrelated
    #: produced neither output and was scored NEUTRAL_FAILURE.
    #:
    #: The damage rate is the abstention suite's headline and it is the number that counts AGAINST
    #: the memory layer, so a measurement error that can only push it down is a self-favouring one,
    #: whoever wrote it. Splitting this out makes the reported harm a BAND (exact matches as the
    #: floor, exact plus ambiguous as the ceiling) instead of a floor presented as a point.
    AMBIGUOUS_FAILURE = "ambiguous_failure"


class ContradictoryVerdicts(RuntimeError):
    """The checker passed while the damage detector fired. One of them is wrong."""


@runtime_checkable
class DamageDetector(Protocol):
    def __call__(
        self, workdir: Path, oracle_dir: Path, condition: str
    ) -> tuple[bool, str]:  # pragma: no cover - structural
        """Return whether the deliverable embodies this condition's planted wrong fact."""


def classify(
    checker_ok: bool, damage_hit: bool, *, naive_match: bool | None = None, detail: str = ""
) -> Outcome:
    """Fold a checker verdict and a damage verdict into one outcome.

    Raises rather than choosing when the two disagree in the impossible direction.

    ``naive_match`` is the detector's third answer: whether a failing deliverable is recognisably
    the FACTLESS one. ``None`` means the detector cannot tell, which is the pre-2026-08-28
    behaviour and keeps every existing caller working; ``False`` on a failing cell produces
    :attr:`Outcome.AMBIGUOUS_FAILURE` rather than silently crediting the arm with a clean miss.
    """

    if checker_ok and damage_hit:
        raise ContradictoryVerdicts(
            "the checker passed and the damage detector fired on the same sandbox: the "
            f"deliverable cannot be both correct and built on the planted wrong fact. {detail}"
        )
    if checker_ok:
        return Outcome.SOLVED
    if damage_hit:
        return Outcome.DAMAGED
    if naive_match is False:
        return Outcome.AMBIGUOUS_FAILURE
    return Outcome.NEUTRAL_FAILURE


def harm_band(outcomes: Sequence[Outcome]) -> dict[str, Any]:
    """The damage rate as an interval, because an exact-match detector can only under-count.

    ``floor`` counts only deliverables that matched the planted outcome exactly. ``ceiling`` adds
    the ones that matched neither reference, every one of which MIGHT be a partially-applied plant.
    The truth is between, and a single number here would be the floor wearing a point estimate's
    clothes.
    """

    if not outcomes:
        raise ValueError("a harm band needs at least one classified cell")
    total = len(outcomes)
    damaged = sum(1 for o in outcomes if o is Outcome.DAMAGED)
    ambiguous = sum(1 for o in outcomes if o is Outcome.AMBIGUOUS_FAILURE)
    return {
        "n_cells": total,
        "damaged": damaged,
        "ambiguous": ambiguous,
        "neutral": sum(1 for o in outcomes if o is Outcome.NEUTRAL_FAILURE),
        "solved": sum(1 for o in outcomes if o is Outcome.SOLVED),
        "damage_rate_floor": round(damaged / total, 4),
        "damage_rate_ceiling": round((damaged + ambiguous) / total, 4),
        "note": (
            "floor counts exact matches against the damaged reference; ceiling adds failures that "
            "matched neither reference and could be a partially applied plant"
        ),
    }


def condition_of(reference: str | Path) -> str:
    """The corpus condition a `reference/damaged_*.py` file applies a plant from.

    `damaged_<condition>.py` is the usual case. A condition whose corpus holds MORE THAN ONE wrong
    memo needs one reference per memo, because a planted signature that no reference ever produces
    is an expectation file that can be wrong with nothing to say so. `contradictory` is the first:
    its two memos disagree, and a detector that only ever saw one side could not show it tells them
    apart. Those take a second segment:

        damaged_contradictory.py            memo A
        damaged_contradictory__lagos.py     memo B, same condition

    The separator is a DOUBLE underscore, so a condition name containing a single one cannot be
    split down the middle. None does today; `wrong_scope` is the obvious next one.
    """

    return Path(reference).stem.removeprefix("damaged_").split("__", 1)[0]


def load_detector_module(task_dir: str | Path):
    """Import ``<task_dir>/damage.py`` whole, or None for a task with no planted conditions.

    `load_detector` wants one function out of it. The gate wants the module, because a detector may
    also declare what its task's FACTLESS outcomes look like, which is how a planted signature is
    checked against the mistakes an agent makes anyway.
    """

    path = Path(task_dir) / "damage.py"
    if not path.is_file():
        return None
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"damage_{Path(task_dir).name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load a damage detector from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_detector(task_dir: str | Path) -> Callable[..., tuple[bool, str]] | None:
    """Load ``<task_dir>/damage.py::detect``, or None for a task with no planted conditions."""

    module = load_detector_module(task_dir)
    if module is None:
        return None
    path = Path(task_dir) / "damage.py"
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
