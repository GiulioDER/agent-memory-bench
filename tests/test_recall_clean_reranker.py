from __future__ import annotations

from pathlib import Path

from scripts.recall_clean_graph_preflight import preflight
from scripts.recall_clean_reranker_confirmation_select import (
    EXPECTED_CELLS as CONFIRMATION_CELLS,
)
from scripts.recall_clean_reranker_confirmation_select import (
    select_confirmation,
)
from scripts.recall_clean_reranker_screen_select import (
    EXPECTED_CELLS as SCREEN_CELLS,
)
from scripts.recall_clean_reranker_screen_select import (
    select_screen,
)
from scripts.recall_clean_reranker_select import (
    CONDITIONS,
    VARIANTS,
    select_clean_retrieval,
)
from scripts.recall_clean_reranker_select import (
    main as retrieval_main,
)

REPO = Path(__file__).resolve().parents[1]


def _retrieval_artifact(condition: str, variant: str) -> dict:
    reranked = variant == "B1_raw_rerank"
    rows = []
    for task_index in range(34):
        for capture in range(3):
            rows.append(
                {
                    "task_id": f"task-{task_index:02d}",
                    "capture": capture,
                    "reranker_fallback": False,
                    "reranker": {
                        "attempted": reranked,
                        "completed": reranked,
                        "provider": "voyage" if reranked else "none",
                        "model": "rerank-2.5" if reranked else "none",
                        "input_count": 100,
                        "output_count": 100,
                        "permutation_valid": True,
                        "served_commit": "abc123",
                        "generation_id": "aml-clean-reranker-v1",
                        "corpus_sha256": condition[0] * 64,
                        "variant": variant,
                    },
                }
            )
    return {
        "variant": variant,
        "namespace": f"clean-{condition}",
        "task_count": 34,
        "capture_count": 3,
        "request_count": 102,
        "dense_embedding_pass": not reranked,
        "corpus_reused": reranked,
        "version": {
            "variant": variant,
            "git_commit": "abc123",
            "embedding_profile": "voyage-context-4-v1",
            "reranker_provider": "voyage",
            "reranker_model": "rerank-2.5",
            "candidate_width": 100,
            "rrf_constant": 60,
        },
        "corpus_status": {
            "corpus_sha256": condition[0] * 64,
            "generation_id": "aml-clean-reranker-v1",
        },
        "aggregate": {
            "mean_reciprocal_rank": 0.4 if reranked else 0.3,
            "complete_coverage_at_100": 1.0,
            "mean_source_session_recall": 1.0,
            "search_p95_ms": 200.0 if reranked else 100.0,
            "estimated_reranker_cost_usd": 0.01 if reranked else 0.0,
        },
        "rows": rows,
    }


def test_graph_preflight_excludes_a_zero_relation_corpus():
    result = preflight(
        {"authored_relation_count": 0, "eligible_relation_count": 0},
        {
            "authored_relation_count": 0,
            "eligible_relation_count": 0,
            "store_relation_count": 0,
        },
    )

    assert result["verdict"] == "ineligible_zero_relations"
    assert result["graph_added_to_matrix"] is False


def test_graph_preflight_pauses_on_unexpected_nonzero_relations():
    result = preflight(
        {"authored_relation_count": 2, "eligible_relation_count": 1},
        {
            "authored_relation_count": 2,
            "eligible_relation_count": 1,
            "store_relation_count": 2,
        },
    )

    assert result["verdict"] == "pause_nonzero_relations"
    assert result["graph_added_to_matrix"] is False


def test_retrieval_selector_enforces_five_dense_passes_and_independent_reranker_gates():
    artifacts = {
        (condition, variant): _retrieval_artifact(condition, variant)
        for condition in CONDITIONS
        for variant in VARIANTS
    }

    result = select_clean_retrieval(artifacts, {"verdict": "ineligible_zero_relations"})

    assert result["screen_authorized"] is True
    assert result["selected"] == "B1_raw_rerank"
    assert result["dense_embedding_passes"] == 5
    assert all(not item["b1_dense_embedding_pass"] for item in result["lineage"].values())


def test_retrieval_selector_stops_when_one_reranker_request_was_not_attempted():
    artifacts = {
        (condition, variant): _retrieval_artifact(condition, variant)
        for condition in CONDITIONS
        for variant in VARIANTS
    }
    artifacts[("present", "B1_raw_rerank")]["rows"][0]["reranker"]["attempted"] = False

    result = select_clean_retrieval(artifacts, {"verdict": "ineligible_zero_relations"})

    assert result["mechanism_gates"]["b1_every_request_attempted"] is False
    assert result["screen_authorized"] is False
    assert result["selected"] == "B0_raw"


def test_screen_selector_requires_positive_cell_wins_and_complete_72_cell_grid():
    baseline = {
        cell: {"success": False, "memory_call_count": 1, "retrieved_contexts": ["evidence"]}
        for cell in SCREEN_CELLS
    }
    candidate = {cell: dict(record) for cell, record in baseline.items()}
    candidate[min(SCREEN_CELLS)]["success"] = True
    runs = {
        "B0_raw": {"records": baseline, "admitted": set(SCREEN_CELLS), "traces": [{}]},
        "B1_raw_rerank": {
            "records": candidate,
            "admitted": set(SCREEN_CELLS),
            "traces": [{}],
        },
    }

    result = select_screen(runs, {"screen_authorized": True})

    assert result["paired_cells"] == 36
    assert result["confirmation_authorized"] is True
    assert result["selected"] == "B1_raw_rerank"


def test_screen_selector_stops_on_a_tie():
    baseline = {
        cell: {"success": False, "memory_call_count": 1, "retrieved_contexts": ["evidence"]}
        for cell in SCREEN_CELLS
    }
    runs = {
        variant: {
            "records": {cell: dict(record) for cell, record in baseline.items()},
            "admitted": set(SCREEN_CELLS),
            "traces": [{}],
        }
        for variant in VARIANTS
    }

    result = select_screen(runs, {"screen_authorized": True})

    assert result["candidate_only_wins"] == result["baseline_only_wins"] == 0
    assert result["confirmation_authorized"] is False
    assert result["selected"] == "B0_raw"


def test_confirmation_selector_requires_positive_task_clustered_ci_and_1020_cells():
    runs = {}
    for condition in CONDITIONS:
        for variant in VARIANTS:
            success = variant == "B1_raw_rerank"
            records = {
                cell: {
                    "success": success,
                    "memory_call_count": 1,
                    "retrieved_contexts": ["evidence"],
                    "metadata": {"outcome": "solved" if success else "neutral_failure"},
                }
                for cell in CONFIRMATION_CELLS
            }
            runs[(condition, variant)] = {
                "records": records,
                "admitted": set(CONFIRMATION_CELLS),
                "traces": [{"headers": {"x-recall-search-ms": "100"}}],
            }
    retrieval = {"screen_authorized": True}
    screen = {"confirmation_authorized": True, "selected": "B1_raw_rerank"}

    result = select_confirmation(runs, retrieval, screen)

    assert result["expected_cells"] == 1_020
    assert result["paired_contrasts"] == 510
    assert result["task_clustered_bootstrap_95_ci"][0] > 0
    assert result["passed"] is True
    assert result["selected"] == "B1_raw_rerank"


def test_confirmation_selector_stops_when_clustered_ci_is_not_positive():
    runs = {}
    for condition in CONDITIONS:
        for variant in VARIANTS:
            records = {
                cell: {
                    "success": False,
                    "memory_call_count": 1,
                    "retrieved_contexts": ["evidence"],
                    "metadata": {"outcome": "neutral_failure"},
                }
                for cell in CONFIRMATION_CELLS
            }
            runs[(condition, variant)] = {
                "records": records,
                "admitted": set(CONFIRMATION_CELLS),
                "traces": [{"headers": {"x-recall-search-ms": "100"}}],
            }

    result = select_confirmation(
        runs,
        {"screen_authorized": True},
        {"confirmation_authorized": True, "selected": "B1_raw_rerank"},
    )

    assert result["task_clustered_bootstrap_95_ci"] == [0.0, 0.0]
    assert result["gates"]["overall_clustered_ci_lower_positive"] is False
    assert result["passed"] is False
    assert result["selected"] == "B0_raw"


def test_retrieval_selector_refuses_to_overwrite_an_immutable_artifact(monkeypatch, tmp_path):
    output = tmp_path / "selection.json"
    output.write_text("frozen\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "recall_clean_reranker_select",
            "--artifacts-root",
            str(tmp_path / "artifacts"),
            "--graph-preflight",
            str(tmp_path / "graph.json"),
            "--output",
            str(output),
        ],
    )

    import pytest

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        retrieval_main()
    assert output.read_text(encoding="utf-8") == "frozen\n"


def test_vps2_wrappers_pass_absolute_condition_corpus_paths():
    for name in (
        "recall_clean_reranker_vps2_replay.sh",
        "recall_clean_reranker_vps2_confirmation.sh",
    ):
        script = (REPO / "scripts" / name).read_text(encoding="utf-8")
        assert 'corpus_root="$(pwd)/corpus/conditions/' in script
