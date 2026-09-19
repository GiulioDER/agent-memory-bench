from scripts.recall_coding_screen_select import EXPECTED_CELLS, select_screen
from scripts.recall_hosted_replay import CODING_MATRIX_VARIANTS


def test_screen_selector_uses_success_then_frozen_retrieval_tiebreakers():
    runs = {}
    for index, name in enumerate(CODING_MATRIX_VARIANTS):
        records = {
            cell: {
                "success": index > 0 if cell == min(EXPECTED_CELLS) else False,
                "memory_call_count": 1,
                "retrieved_contexts": ["evidence"],
            }
            for cell in EXPECTED_CELLS
        }
        runs[name] = {
            "records": records,
            "admitted": set(EXPECTED_CELLS),
            "invalid_cells": 0,
            "estimated_usd": 1.0,
        }
    retrieval = {
        "deepest_retrieval_eligible": "C4_task_pack",
        "variants": {
            name: {
                "complete_coverage_at_10": 0.5,
                "mean_reciprocal_rank": 0.5,
                "mean_character_count": 10_000 - index,
                "search_p95_ms": 100,
            }
            for index, name in enumerate(CODING_MATRIX_VARIANTS)
        },
    }

    selected = select_screen(runs, retrieval)

    assert selected["promoted_candidate"] == "C4_task_pack"
    assert selected["variants"]["C4_task_pack"]["net_wins"] == 1
    assert selected["common_admitted_cells"] == 36
