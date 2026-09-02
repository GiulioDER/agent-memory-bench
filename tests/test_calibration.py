from __future__ import annotations

import pytest

from harness.calibration import (
    CalibrationExample,
    calibrate,
    examples_from_records,
    expected_calibration_error,
    fit_threshold,
    roc_auc,
)


def examples(pos: list[float], neg: list[float]) -> list[CalibrationExample]:
    return [
        CalibrationExample(f"p{index}", score, True) for index, score in enumerate(pos)
    ] + [CalibrationExample(f"n{index}", score, False) for index, score in enumerate(neg)]


def test_auc_gives_half_credit_for_ties() -> None:
    assert roc_auc(examples([0.9, 0.5], [0.5, 0.1])) == pytest.approx(0.875)


def test_threshold_reports_answer_and_abstain_errors() -> None:
    result = fit_threshold(examples([0.8, 0.9], [0.1, 0.2]))
    assert result["threshold"] == 0.8
    assert result["sensitivity"] == 1.0
    assert result["specificity"] == 1.0
    assert result["false_accept_rate"] == 0.0
    assert result["false_abstain_rate"] == 0.0


def test_ece_uses_fixed_bins_and_answerability_labels() -> None:
    data = examples([0.9], [0.1])
    assert expected_calibration_error(data, bins=10) == pytest.approx(0.1)


def test_small_calibration_is_reported_but_not_certified() -> None:
    result = calibrate(examples([0.9, 0.8], [0.1, 0.2]), draws=100)
    assert result["auc"] == 1.0
    assert result["status"] == "uncertified"
    assert result["runtime_use"] == "blocked"
    assert any("requires 20" in reason for reason in result["certification_reasons"])


def test_string_labels_are_rejected_instead_of_coerced() -> None:
    with pytest.raises(TypeError, match="answerable must be a bool"):
        CalibrationExample.from_mapping(
            {"id": "x", "confidence": 0.5, "answerable": "false"}
        )


def test_duplicate_ids_are_rejected() -> None:
    data = [
        CalibrationExample("same", 0.9, True),
        CalibrationExample("same", 0.1, False),
    ]
    with pytest.raises(ValueError, match="ids must be unique"):
        calibrate(data, draws=10)


def test_record_confidence_is_joined_to_an_external_label() -> None:
    records = [
        {
            "task_id": "t1",
            "seed": 0,
            "arm": "recall",
            "runtime_decisions": [
                {"confidence": 0.7, "source": "runtime", "decision": "answer"}
            ],
        }
    ]
    result = examples_from_records(
        ({**record} for record in records), {"t1/0/recall": True}
    )
    assert result[0].confidence == 0.7
    assert result[0].answerable is True


def test_record_without_confidence_is_not_a_calibration_observation() -> None:
    records = [{"task_id": "t1", "seed": 0, "arm": "recall", "runtime_decisions": []}]
    assert examples_from_records(records, {"t1/0/recall": True}) == []


def test_twenty_perfect_examples_clear_the_certification_gate() -> None:
    result = calibrate(examples([0.8] * 20, [0.2] * 20), draws=100)
    assert result["auc"] == 1.0
    assert result["auc_ci"] == [1.0, 1.0]
    assert result["certified"] is True
    assert result["runtime_use"] == "eligible"
