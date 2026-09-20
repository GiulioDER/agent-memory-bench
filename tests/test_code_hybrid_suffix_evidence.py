from scripts.code_hybrid_suffix_evidence import (
    EVIDENCE_K,
    PROTECTED_PREFIX_K,
    evaluate_gate,
    hybrid_rankings,
)


def test_hybrid_rankings_select_promotion_and_code4_unique_slot() -> None:
    code = list(range(100))
    context = [2, 4, 20, 6, 100, 21]
    control, treatment, promotion, novel = hybrid_rankings(code, context)
    assert control == list(range(EVIDENCE_K))
    assert treatment[:PROTECTED_PREFIX_K] == list(range(PROTECTED_PREFIX_K))
    assert promotion == 20
    assert novel == 100
    assert treatment[10:] == [20, 100]


def test_hybrid_rankings_use_distinct_unique_candidate_when_promotion_is_unique() -> None:
    code = list(range(100))
    context = [2, 100, 101]
    _, treatment, promotion, novel = hybrid_rankings(code, context)
    assert promotion == 100
    assert novel == 101
    assert treatment[10:] == [100, 101]


def _gate_row(index: int) -> dict[str, object]:
    return {
        "task_id": f"task-{index}",
        "control_count": EVIDENCE_K,
        "treatment_count": EVIDENCE_K,
        "prefix_identical": True,
        "promotion_absent_from_prefix": True,
        "novel_absent_from_code4_top100": True,
        "suffix_distinct": True,
        "control_recall_at_10": True,
        "control_recall_at_12": True,
        "treatment_recall_at_12": True,
        "control_all_shards_at_12": True,
        "treatment_all_shards_at_12": True,
        "promotion_slot_relevant": index < 10,
        "novel_slot_relevant": index < 8,
        "treatment_new_relevant_vs_control": index < 8,
        "control_tokens": 1_000,
        "treatment_tokens": 1_030,
    }


def test_hybrid_evidence_gate_enforces_novelty_thresholds() -> None:
    metrics, gate = evaluate_gate([_gate_row(index) for index in range(34)])
    assert metrics["novel_slot_relevant_queries"] == 8
    assert metrics["new_relevant_vs_control_queries"] == 8
    assert gate["passed"] is True


def test_hybrid_evidence_gate_rejects_candidate_inside_code4_top100() -> None:
    rows = [_gate_row(index) for index in range(34)]
    rows[0]["novel_absent_from_code4_top100"] = False
    _, gate = evaluate_gate(rows)
    assert gate["g3_valid_distinct_hybrid_slots"] is False
    assert gate["passed"] is False
