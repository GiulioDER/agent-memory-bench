from scripts.recall_coding_final_select import EXPECTED_CELLS, select_final


def test_final_selector_requires_eight_net_wins_and_complete_admission():
    baseline_records = {
        cell: {"success": False} for cell in EXPECTED_CELLS
    }
    candidate_records = {
        cell: {"success": index < 8}
        for index, cell in enumerate(sorted(EXPECTED_CELLS))
    }
    baseline = {"records": baseline_records, "admitted": set(EXPECTED_CELLS)}
    candidate = {"records": candidate_records, "admitted": set(EXPECTED_CELLS)}

    result = select_final(baseline, candidate, "C4_task_pack")

    assert result["paired_cells"] == 102
    assert result["net_wins"] == 8
    assert result["passed"] is True
