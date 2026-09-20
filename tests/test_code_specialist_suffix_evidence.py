from scripts.code_specialist_suffix_evidence import (
    EVIDENCE_K,
    PROTECTED_PREFIX_K,
    SUFFIX_K,
    evaluate_gate,
    protected_rankings,
)


def test_protected_rankings_preserve_prefix_and_replace_only_suffix() -> None:
    code = list(range(100))
    context = [2, 4, 100, 6, 101, 7]
    control, treatment, suffix = protected_rankings(code, context)
    assert control == list(range(EVIDENCE_K))
    assert treatment[:PROTECTED_PREFIX_K] == list(range(PROTECTED_PREFIX_K))
    assert suffix == [100, 101]
    assert treatment[PROTECTED_PREFIX_K:] == suffix


def test_protected_rankings_refuse_missing_context_candidates() -> None:
    try:
        protected_rankings(list(range(12)), list(range(10)))
    except ValueError as error:
        assert "two unique suffix" in str(error)
    else:
        raise AssertionError("an incomplete specialist suffix was accepted")


def _gate_row(index: int) -> dict[str, object]:
    return {
        "task_id": f"task-{index}",
        "control_count": EVIDENCE_K,
        "treatment_count": EVIDENCE_K,
        "prefix_identical": True,
        "treatment_suffix_count": SUFFIX_K,
        "treatment_unique": True,
        "control_recall_at_10": True,
        "control_recall_at_12": True,
        "treatment_recall_at_12": True,
        "control_all_shards_at_12": True,
        "treatment_all_shards_at_12": True,
        "treatment_suffix_has_relevant": index < 12,
        "treatment_new_relevant_vs_control": index < 8,
        "any_suffix_in_code4_top100": index % 2 == 0,
        "control_tokens": 1_000,
        "treatment_tokens": 1_020,
    }


def test_evidence_gate_enforces_frozen_thresholds() -> None:
    metrics, gate = evaluate_gate([_gate_row(index) for index in range(34)])
    assert metrics["relevant_context_suffix_queries"] == 12
    assert metrics["new_relevant_vs_control_queries"] == 8
    assert gate["passed"] is True


def test_evidence_gate_rejects_one_prefix_change() -> None:
    rows = [_gate_row(index) for index in range(34)]
    rows[0]["prefix_identical"] = False
    _, gate = evaluate_gate(rows)
    assert gate["g2_protected_prefix_identical"] is False
    assert gate["passed"] is False
