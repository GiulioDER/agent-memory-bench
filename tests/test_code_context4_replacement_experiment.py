from types import SimpleNamespace

import pytest

from scripts.code_context4_replacement_experiment import (
    OUTPUT_DIMENSION,
    VoyageContext4,
    compare_rankings,
    document_parts,
    request_batches,
    summarize,
    validate_frozen_configuration,
)
from scripts.retrieval_probe import Window


def test_document_grouping_keeps_sessions_separate_and_window_order_stable() -> None:
    windows = [
        Window("sessions/a/one.jsonl", "a" * 6),
        Window("sessions/a/one.jsonl", "b" * 6),
        Window("sessions/b/two.jsonl", "c" * 4),
    ]
    parts = document_parts(windows, max_request_chars=10, max_request_chunks=10)
    assert [(part.doc, part.indices) for part in parts] == [
        ("sessions/a/one.jsonl", (0,)),
        ("sessions/a/one.jsonl", (1,)),
        ("sessions/b/two.jsonl", (2,)),
    ]
    batches = request_batches(parts, max_request_chars=10, max_request_chunks=10)
    assert [[part.indices for part in batch] for batch in batches] == [
        [(0,)],
        [(1,), (2,)],
    ]


class _FakeContextClient:
    def count_tokens(self, texts, model):
        assert model == "voyage-context-4"
        return len(texts)

    def contextualized_embed(self, *, inputs, model, input_type, **kwargs):
        assert model == "voyage-context-4"
        if input_type == "query":
            vector = [0.0] * OUTPUT_DIMENSION
            vector[0] = 1.0
            return SimpleNamespace(results=[SimpleNamespace(embeddings=[vector])])
        groups = []
        for group_number, group in enumerate(inputs, start=1):
            vectors = []
            for chunk_number, _ in enumerate(group, start=1):
                vector = [0.0] * OUTPUT_DIMENSION
                vector[0] = float(group_number + chunk_number)
                vectors.append(vector)
            groups.append(SimpleNamespace(embeddings=vectors))
        return SimpleNamespace(results=groups)


def test_context_embedder_preserves_one_vector_per_raw_window() -> None:
    windows = [
        Window("sessions/a/one.jsonl", "alpha"),
        Window("sessions/a/one.jsonl", "beta"),
        Window("sessions/b/two.jsonl", "gamma"),
    ]
    backend = VoyageContext4(
        windows,
        "voyage-context-4",
        500_000,
        client=_FakeContextClient(),
    )
    assert backend.matrix.shape == (3, OUTPUT_DIMENSION)
    assert set(backend.scores("query")) == {0, 1, 2}
    assert backend.grouping_diagnostics["documents"] == 2
    assert backend.grouping_diagnostics["split_documents"] == 0


def test_comparison_reports_prefix_novelty_and_complete_shards() -> None:
    windows = [
        Window("sessions/x/a.jsonl", "a"),
        Window("sessions/x/b.jsonl", "b"),
        Window("sessions/y/c.jsonl", "c"),
        Window("sessions/z/d.jsonl", "d"),
    ]
    row = compare_rankings(
        [0, 2, 3, 1],
        [1, 2, 3, 0],
        {0, 1},
        {"sessions/x/a.jsonl", "sessions/x/b.jsonl"},
        windows,
    )
    assert row["rank_relation"] == "tie"
    assert row["at_10"]["treatment_new_relevant_windows"] == []
    assert row["control_all_shards_at_10"] is True
    assert row["treatment_all_shards_at_10"] is True


def _row(control_rank: int, treatment_rank: int, *, treatment_novel: bool) -> dict:
    relation = (
        "win"
        if treatment_rank < control_rank
        else "tie"
        if treatment_rank == control_rank
        else "regression"
    )
    row = {
        "control_rank": control_rank,
        "treatment_rank": treatment_rank,
        "rank_relation": relation,
        "control_response_tokens_at_100": 1_000,
        "treatment_response_tokens_at_100": 1_000,
    }
    for k in (1, 3, 5, 10, 20, 100):
        row[f"control_recall_at_{k}"] = control_rank <= k
        row[f"treatment_recall_at_{k}"] = treatment_rank <= k
    for k in (10, 20, 100):
        row[f"at_{k}"] = {
            "overlap": k // 2,
            "union": k,
            "jaccard": 0.5,
            "treatment_new_relevant_windows": [99] if treatment_novel else [],
            "control_new_relevant_windows": [],
        }
        row[f"control_all_shards_at_{k}"] = True
        row[f"treatment_all_shards_at_{k}"] = True
    return row


def test_summary_separates_direct_replacement_and_protected_fusion_gates() -> None:
    rows = [_row(2, 1, treatment_novel=True) for _ in range(34)]
    metrics, predictions, decisions = summarize(
        rows,
        control_latency=[10.0] * 34,
        treatment_latency=[12.0] * 34,
    )
    assert metrics["source_recall"]["at_10"]["treatment_count"] == 34
    assert predictions["p5_context_new_relevant_top100_at_least_3"] is True
    assert decisions["direct_replacement_passed"] is True
    assert decisions["protected_fusion_preregistration_licensed"] is True


def test_fusion_can_be_licensed_when_direct_replacement_fails() -> None:
    rows = [_row(1, 2, treatment_novel=index < 3) for index in range(34)]
    _, _, decisions = summarize(
        rows,
        control_latency=[10.0] * 34,
        treatment_latency=[12.0] * 34,
    )
    assert decisions["direct_replacement_passed"] is False
    assert decisions["protected_fusion_preregistration_licensed"] is True


def test_runtime_cannot_change_frozen_models_or_depth() -> None:
    with pytest.raises(ValueError, match="fixes Code 4 and Context 4"):
        validate_frozen_configuration(
            control_model="voyage-code-3",
            treatment_model="voyage-context-4",
            max_tokens_per_model=500_000,
            candidate_k=100,
            result_k=100,
        )
    with pytest.raises(ValueError, match="candidate_k"):
        validate_frozen_configuration(
            control_model="voyage-code-4",
            treatment_model="voyage-context-4",
            max_tokens_per_model=500_000,
            candidate_k=50,
            result_k=100,
        )
