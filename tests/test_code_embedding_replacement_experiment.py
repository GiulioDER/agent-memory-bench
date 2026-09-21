from scripts.code_embedding_replacement_experiment import (
    compare_rankings,
    fused_ranking,
    summarize,
    validate_frozen_configuration,
)


def test_each_model_fuses_only_with_the_shared_lexical_ranking() -> None:
    """Red 2026-09-20: combining both dense ranks would make this test return the same head."""

    lexical = [3, 1, 0, 2]
    control = fused_ranking({0: 1.0, 1: 0.9, 2: 0.1, 3: 0.0}, lexical, result_k=4)
    treatment = fused_ranking({2: 1.0, 1: 0.9, 0: 0.1, 3: 0.0}, lexical, result_k=4)
    assert control != treatment
    assert control.index(0) < treatment.index(0)
    assert treatment.index(2) < control.index(2)


def test_comparison_records_rank_regression_and_symmetric_novelty() -> None:
    """Red 2026-09-20: one-way novelty hid relevant windows unique to the control."""

    row = compare_rankings([4, 1, 2], [5, 2, 1], {1, 4, 5}, result_k=3)
    assert row["control_rank"] == 1
    assert row["treatment_rank"] == 1
    assert row["rank_relation"] == "tie"
    assert row["treatment_new_relevant_windows"] == [5]
    assert row["control_new_relevant_windows"] == [4]
    assert row["top100_overlap"] == 2
    assert row["top100_union"] == 4
    assert row["top100_jaccard"] == 0.5


def test_summary_keeps_replacement_and_future_fusion_gates_separate() -> None:
    """Red 2026-09-20: candidate novelty alone incorrectly licensed Task Solve."""

    rows = []
    for index in range(4):
        control_rank = 5 if index < 2 else 20
        treatment_rank = 2 if index < 3 else 20
        rows.append(
            {
                "control_rank": control_rank,
                "treatment_rank": treatment_rank,
                "rank_relation": "win" if treatment_rank < control_rank else "tie",
                "treatment_new_relevant_windows": [100 + index],
                "control_new_relevant_windows": [],
                "top100_jaccard": 0.5,
                "control_response_tokens_at_100": 1000,
                "treatment_response_tokens_at_100": 1000,
                **{
                    f"control_recall_at_{k}": control_rank <= k
                    for k in (1, 3, 5, 10, 20, 100)
                },
                **{
                    f"treatment_recall_at_{k}": treatment_rank <= k
                    for k in (1, 3, 5, 10, 20, 100)
                },
            }
        )

    metrics, predictions, decisions = summarize(
        rows,
        control_latency=[10.0] * 4,
        treatment_latency=[12.0] * 4,
    )
    assert metrics["source_recall"]["at_10"]["delta_queries"] == 1
    assert predictions["p5_new_relevant_queries_at_least_3"] is True
    assert decisions["protected_rescue_preregistration_licensed"] is True
    assert decisions["direct_replacement_passed"] is True
    assert decisions["task_solve_screen_licensed"] is True


def test_replacement_fails_when_rank_regressions_outnumber_wins() -> None:
    rows = []
    for control_rank, treatment_rank in ((1, 2), (2, 3), (20, 2)):
        relation = "win" if treatment_rank < control_rank else "regression"
        rows.append(
            {
                "control_rank": control_rank,
                "treatment_rank": treatment_rank,
                "rank_relation": relation,
                "treatment_new_relevant_windows": [],
                "control_new_relevant_windows": [],
                "top100_jaccard": 1.0,
                "control_response_tokens_at_100": 1000,
                "treatment_response_tokens_at_100": 1000,
                **{
                    f"control_recall_at_{k}": control_rank <= k
                    for k in (1, 3, 5, 10, 20, 100)
                },
                **{
                    f"treatment_recall_at_{k}": treatment_rank <= k
                    for k in (1, 3, 5, 10, 20, 100)
                },
            }
        )

    _, _, decisions = summarize(
        rows,
        control_latency=[10.0] * 3,
        treatment_latency=[11.0] * 3,
    )
    assert decisions["direct_replacement_passed"] is False
    assert decisions["task_solve_screen_licensed"] is False


def test_runtime_cannot_change_the_frozen_models_or_candidate_depth() -> None:
    """Red 2026-09-20: CLI overrides could silently run a different experiment."""

    try:
        validate_frozen_configuration(
            control_model="voyage-context-4",
            treatment_model="voyage-code-4",
            max_tokens_per_model=500_000,
            candidate_k=100,
            result_k=100,
        )
    except ValueError as error:
        assert "fixes voyage-code-3" in str(error)
    else:
        raise AssertionError("the frozen control-model override was accepted")

    try:
        validate_frozen_configuration(
            control_model="voyage-code-3",
            treatment_model="voyage-code-4",
            max_tokens_per_model=500_000,
            candidate_k=50,
            result_k=100,
        )
    except ValueError as error:
        assert "candidate_k" in str(error)
    else:
        raise AssertionError("the frozen candidate depth override was accepted")
