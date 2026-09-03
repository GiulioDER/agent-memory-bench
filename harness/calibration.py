"""Calibration and discrimination metrics for answerability confidence scores.

This is deliberately separate from :mod:`harness.decision_trace`. A trace contract asks whether
the runtime followed its own abstain-or-escalate rule. Calibration asks whether confidence scores
separate answerable from unanswerable cases and whether those scores behave like probabilities.

The score convention is fixed here: larger confidence means more likely answerable. A threshold
therefore answers when ``confidence >= threshold`` and abstains below it. An uncertified result is
reported, never silently promoted into a runtime policy.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

MIN_SAMPLES_PER_CLASS = 20
MIN_CERTIFIED_AUC_LOWER_BOUND = 0.90
DEFAULT_BOOTSTRAP_DRAWS = 10_000


def _score(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("confidence must be a number in [0, 1]")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError("confidence must be a finite number in [0, 1]")
    return number


def _valid_score(value: Any) -> bool:
    try:
        _score(value)
    except (TypeError, ValueError):
        return False
    return True


@dataclass(frozen=True)
class CalibrationExample:
    """One independently labelled answerability example."""

    example_id: str
    confidence: float
    answerable: bool
    source: str = ""

    def __post_init__(self) -> None:
        if not self.example_id.strip():
            raise ValueError("example_id must not be empty")
        _score(self.confidence)
        if not isinstance(self.answerable, bool):
            raise TypeError("answerable must be a bool")

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> CalibrationExample:
        """Load the small JSON shape accepted by the calibration CLI."""

        answerable = value.get("answerable")
        if not isinstance(answerable, bool):
            raise TypeError("answerable must be a bool")
        return cls(
            example_id=str(value.get("id", value.get("example_id", ""))),
            confidence=_score(value.get("confidence")),
            answerable=answerable,
            source=str(value.get("source", "")),
        )


def _split(examples: Sequence[CalibrationExample]) -> tuple[list[float], list[float]]:
    positives = [example.confidence for example in examples if example.answerable]
    negatives = [example.confidence for example in examples if not example.answerable]
    if not positives or not negatives:
        raise ValueError("AUC requires at least one answerable and one unanswerable example")
    return positives, negatives


def roc_auc(examples: Sequence[CalibrationExample]) -> float:
    """Compute ROC AUC by the probability that a positive outranks a negative.

    Ties contribute one half, so the result is defined even when a threshold produces many equal
    scores. This is equivalent to the Mann-Whitney formulation and needs no third-party package.
    """

    positives, negatives = _split(examples)
    wins = sum(
        1.0 if positive > negative else 0.5 if positive == negative else 0.0
        for positive in positives
        for negative in negatives
    )
    return wins / (len(positives) * len(negatives))


def bootstrap_auc_ci(
    examples: Sequence[CalibrationExample],
    *,
    draws: int = DEFAULT_BOOTSTRAP_DRAWS,
    seed: int = 20260902,
    confidence: float = 0.95,
) -> list[float] | None:
    """Return a deterministic percentile bootstrap interval for AUC.

    Sampling within each class preserves both classes in every draw. ``None`` is returned for a
    one-example class because that interval would be a statement about a single observation.
    """

    if draws <= 0:
        raise ValueError("draws must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    positives, negatives = _split(examples)
    if len(positives) < 2 or len(negatives) < 2:
        return None
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(draws):
        sample = [
            CalibrationExample(f"p{index}", positives[rng.randrange(len(positives))], True)
            for index in range(len(positives))
        ]
        sample.extend(
            CalibrationExample(f"n{index}", negatives[rng.randrange(len(negatives))], False)
            for index in range(len(negatives))
        )
        values.append(roc_auc(sample))
    values.sort()
    lower = (1.0 - confidence) / 2.0
    upper = 1.0 - lower

    def percentile(q: float) -> float:
        position = q * (len(values) - 1)
        left = math.floor(position)
        right = math.ceil(position)
        if left == right:
            return values[left]
        weight = position - left
        return values[left] * (1.0 - weight) + values[right] * weight

    return [round(percentile(lower), 6), round(percentile(upper), 6)]


def threshold_metrics(
    examples: Sequence[CalibrationExample], threshold: float
) -> dict[str, float | int]:
    """Report the answer or abstain confusion matrix at one threshold."""

    threshold = _score(threshold)
    positives, negatives = _split(examples)
    tp = sum(score >= threshold for score in positives)
    fn = len(positives) - tp
    tn = sum(score < threshold for score in negatives)
    fp = len(negatives) - tn
    sensitivity = tp / len(positives)
    specificity = tn / len(negatives)
    return {
        "threshold": threshold,
        "true_positive": tp,
        "false_negative": fn,
        "true_negative": tn,
        "false_positive": fp,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "false_abstain_rate": 1.0 - sensitivity,
        "false_accept_rate": 1.0 - specificity,
        "youden_j": sensitivity + specificity - 1.0,
    }


def fit_threshold(examples: Sequence[CalibrationExample]) -> dict[str, float | int]:
    """Choose the threshold with maximum Youden J and a deterministic safety tie-break.

    Ties prefer specificity, then sensitivity, then the lower threshold. This keeps the choice
    reproducible and makes the tie-break explicit rather than letting input order decide it.
    """

    candidates = sorted({0.0, 1.0, *(example.confidence for example in examples)})
    metrics = [threshold_metrics(examples, candidate) for candidate in candidates]
    return max(
        metrics,
        key=lambda item: (
            float(item["youden_j"]),
            float(item["specificity"]),
            float(item["sensitivity"]),
            -float(item["threshold"]),
        ),
    )


def brier_score(examples: Sequence[CalibrationExample]) -> float:
    """Mean squared error of confidence as a probability of answerability."""

    if not examples:
        raise ValueError("at least one calibration example is required")
    return sum(
        (example.confidence - int(example.answerable)) ** 2 for example in examples
    ) / len(examples)


def expected_calibration_error(
    examples: Sequence[CalibrationExample], *, bins: int = 10
) -> float:
    """Fixed-width expected calibration error over confidence bins."""

    if not examples:
        raise ValueError("at least one calibration example is required")
    if bins <= 0:
        raise ValueError("bins must be positive")
    grouped: list[list[CalibrationExample]] = [[] for _ in range(bins)]
    for example in examples:
        index = min(int(example.confidence * bins), bins - 1)
        grouped[index].append(example)
    total = len(examples)
    return sum(
        len(group) / total
        * abs(
            sum(example.confidence for example in group) / len(group)
            - sum(example.answerable for example in group) / len(group)
        )
        for group in grouped
        if group
    )


def calibrate(
    examples: Iterable[CalibrationExample],
    *,
    draws: int = DEFAULT_BOOTSTRAP_DRAWS,
    seed: int = 20260902,
) -> dict[str, Any]:
    """Return metrics and an explicit certification verdict for a labelled query set."""

    materialized = tuple(examples)
    if len({example.example_id for example in materialized}) != len(materialized):
        raise ValueError("calibration example ids must be unique")
    positives, negatives = _split(materialized)
    auc = roc_auc(materialized)
    auc_ci = bootstrap_auc_ci(materialized, draws=draws, seed=seed)
    fitted = fit_threshold(materialized)
    reasons: list[str] = []
    if len(positives) < MIN_SAMPLES_PER_CLASS:
        reasons.append(
            f"answerable class has {len(positives)} samples, requires {MIN_SAMPLES_PER_CLASS}"
        )
    if len(negatives) < MIN_SAMPLES_PER_CLASS:
        reasons.append(
            f"unanswerable class has {len(negatives)} samples, requires {MIN_SAMPLES_PER_CLASS}"
        )
    if auc_ci is None or auc_ci[0] < MIN_CERTIFIED_AUC_LOWER_BOUND:
        lower = "unknown" if auc_ci is None else f"{auc_ci[0]:.3f}"
        reasons.append(
            f"AUC lower bound {lower} is below {MIN_CERTIFIED_AUC_LOWER_BOUND:.2f}"
        )
    certified = not reasons
    return {
        "status": "certified" if certified else "uncertified",
        "certified": certified,
        "certification_reasons": reasons,
        "n_samples": len(materialized),
        "n_answerable": len(positives),
        "n_unanswerable": len(negatives),
        "auc": round(auc, 6),
        "auc_ci": auc_ci,
        "threshold": fitted,
        "brier_score": round(brier_score(materialized), 6),
        "expected_calibration_error": round(expected_calibration_error(materialized), 6),
        "runtime_use": "eligible" if certified else "blocked",
    }


def examples_from_records(
    records: Iterable[Mapping[str, Any]], labels: Mapping[str, bool]
) -> list[CalibrationExample]:
    """Join recorded confidence events to labels kept outside the session record.

    The label key is ``<task_id>/<seed>/<arm>``. A multi-condition report may use
    ``<condition>/<task_id>/<seed>/<arm>`` and that scoped key takes precedence. Labels stay in a separate file so gold answers
    cannot reach the runtime and so calibration can be screened or reviewed independently. If a
    session emitted several decisions, the last decision carrying a valid confidence is the one
    used for that session's terminal outcome.
    """

    from .decision_trace import decisions_from_record

    examples: list[CalibrationExample] = []
    for record in records:
        base_key = f"{record.get('task_id')}/{record.get('seed', 0)}/{record.get('arm')}"
        metadata = record.get("metadata")
        condition = record.get("condition")
        if condition is None and isinstance(metadata, Mapping):
            condition = metadata.get("condition")
        scoped_key = f"{condition}/{base_key}" if condition else None
        key = scoped_key if scoped_key in labels else base_key
        answerable = labels.get(key)
        if not isinstance(answerable, bool):
            continue
        decisions = decisions_from_record(record)
        scored = [
            decision
            for decision in decisions
            if _valid_score(decision.get("confidence"))
        ]
        if not scored:
            continue
        decision = scored[-1]
        examples.append(
            CalibrationExample(
                example_id=key,
                confidence=_score(decision["confidence"]),
                answerable=answerable,
                source=str(decision.get("source", key)),
            )
        )
    return examples
