from __future__ import annotations

from pathlib import Path

from scripts.recall_code_aware_confirmation_select import (
    EXPECTED_CELLS as CONFIRMATION_CELLS,
)
from scripts.recall_code_aware_confirmation_select import select_confirmation
from scripts.recall_code_aware_robustness_select import CONDITIONS, select_robustness
from scripts.recall_code_aware_screen_select import EXPECTED_CELLS as SCREEN_CELLS
from scripts.recall_code_aware_screen_select import select_screen
from scripts.recall_code_aware_select import select_code_aware


def _artifact(variant: str, *, candidate: bool) -> dict:
    rows = []
    for task_index in range(34):
        for capture in range(3):
            rows.append(
                {
                    "task_id": f"task-{task_index:02d}",
                    "capture": capture,
                    "query_sha256": f"q{task_index:063d}",
                    "fact_terms_sha256": f"f{task_index:063d}",
                    "code_aware": {
                        "attempted": candidate,
                        "fallback": False,
                        "profile": "aml-code-exact-v1" if candidate else "none",
                        "rrf_weight": 0.5 if candidate else 0.0,
                        "query_token_count": 3 if candidate else 0,
                        "match_candidate_count": 2 if candidate else 0,
                        "top_10_order_changed": candidate,
                        "top_10_membership_changed": candidate,
                        "top_100_order_changed": candidate,
                        "top_100_membership_changed": False,
                        "neighbour_seed_limit": 8 if candidate else 0,
                        "neighbour_seed_count": 1 if candidate else 0,
                        "neighbour_activated_seed_count": 1 if candidate else 0,
                        "neighbour_ineligible_seed_count": 0,
                        "neighbour_restored_count": 2 if candidate else 0,
                        "neighbour_invalid_count": 0,
                        "duplicate_output_count": 0,
                        "served_commit": "abc123",
                        "generation_id": "aml-code-aware-raw-v1",
                        "corpus_sha256": "c" * 64,
                        "variant": variant,
                    },
                }
            )
    aggregate = {
        "mean_reciprocal_rank": 0.35 if candidate else 0.30,
        "complete_coverage_at_10": 0.20,
        "complete_coverage_at_100": 0.95,
        "mean_source_session_recall": 1.0,
        "search_p95_ms": 500.0 if candidate else 300.0,
    }
    return {
        "schema_version": 3,
        "variant": variant,
        "namespace": "shared-present",
        "version": {
            "variant": variant,
            "git_commit": "abc123",
            "embedding_profile": "voyage-context-4-v1",
            "candidate_width": 100,
            "rrf_constant": 60,
            "code_profile": "aml-code-exact-v1",
            "code_rrf_weight": 0.5,
            "code_neighbour_seed_limit": 8,
            "code_neighbour_predecessor_radius": 1,
            "code_neighbour_successor_radius": 1,
        },
        "corpus_manifest_sha256": "m" * 64,
        "task_set_sha256": "t" * 64,
        "task_count": 34,
        "capture_count": 3,
        "request_count": 102,
        "corpus_reused": candidate,
        "dense_embedding_pass": not candidate,
        "corpus_status": {
            "corpus_sha256": "c" * 64,
            "generation_id": "aml-code-aware-raw-v1",
        },
        "aggregate": aggregate,
        "rows": rows,
    }


def test_selector_promotes_only_a_mechanically_active_candidate():
    selected = select_code_aware(
        {
            "M0_raw": _artifact("M0_raw", candidate=False),
            "M1_code_neighbors": _artifact("M1_code_neighbors", candidate=True),
        }
    )

    assert selected["selected"] == "M1_code_neighbors"
    assert selected["screen_authorized"] is True
    assert len(selected["changed_tasks"]) == 34
    assert len(selected["neighbour_tasks"]) == 34
    assert len(selected["tokenized_tasks"]) == 34
    assert all(selected["mechanism_gates"].values())
    assert all(selected["retrieval_gates"].values())


def test_selector_stops_on_a_single_code_fallback():
    baseline = _artifact("M0_raw", candidate=False)
    candidate = _artifact("M1_code_neighbors", candidate=True)
    candidate["rows"][0]["code_aware"]["fallback"] = True

    selected = select_code_aware({"M0_raw": baseline, "M1_code_neighbors": candidate})

    assert selected["selected"] == "M0_raw"
    assert selected["screen_authorized"] is False
    assert selected["mechanism_gates"]["m1_stage_exact"] is False


def test_selector_stops_when_m1_loses_rank_ten_coverage():
    baseline = _artifact("M0_raw", candidate=False)
    candidate = _artifact("M1_code_neighbors", candidate=True)
    candidate["aggregate"]["complete_coverage_at_10"] = 0.19

    selected = select_code_aware({"M0_raw": baseline, "M1_code_neighbors": candidate})

    assert selected["selected"] == "M0_raw"
    assert selected["retrieval_gates"]["present_coverage_10_nondecline"] is False


def test_vps2_wrapper_uses_fresh_absolute_condition_corpus_and_exact_reuse():
    source = (
        Path(__file__).parents[1] / "scripts" / "recall_code_aware_vps2_retrieval.sh"
    ).read_text(encoding="utf-8")

    assert 'corpus_root="$(pwd)/corpus/conditions/' in source
    assert "run_variant M0_raw" in source
    assert 'run_variant M1_code_neighbors "$corpus_hash"' in source
    assert "--expected-corpus-sha256" in source
    assert "--captures 3" in source


def _execution_run(cells: frozenset[tuple[str, int]], *, candidate: bool) -> dict:
    records = {}
    for task, seed in cells:
        records[(task, seed)] = {
            "success": seed <= (1 if candidate else 0),
            "memory_call_count": 1,
            "retrieved_contexts": ["evidence"],
            "metadata": {"outcome": "correct"},
        }
    return {
        "records": records,
        "admitted": set(cells),
        "traces": [
            {
                "wall_time_ms": 400.0 if candidate else 300.0,
                "headers": {"x-recall-code-aware-fallback": "0"},
            }
            for _ in cells
        ],
        "estimated_usd": 0.01,
    }


def test_screen_selector_promotes_positive_cell_and_task_wins():
    selected = select_screen(
        {
            "M0_raw": _execution_run(SCREEN_CELLS, candidate=False),
            "M1_code_neighbors": _execution_run(SCREEN_CELLS, candidate=True),
        },
        {"screen_authorized": True, "selected": "M1_code_neighbors"},
    )

    assert selected["selected"] == "M1_code_neighbors"
    assert selected["confirmation_authorized"] is True
    assert selected["paired_cells"] == 36
    assert selected["candidate_only_wins"] == 12
    assert selected["baseline_only_wins"] == 0
    assert all(selected["gates"].values())


def test_screen_selector_stops_when_one_task_regresses_by_two_seeds():
    baseline = _execution_run(SCREEN_CELLS, candidate=False)
    candidate = _execution_run(SCREEN_CELLS, candidate=True)
    task = next(iter(sorted(task for task, _ in SCREEN_CELLS)))
    for seed in range(3):
        baseline["records"][(task, seed)]["success"] = seed < 2
        candidate["records"][(task, seed)]["success"] = False

    selected = select_screen(
        {"M0_raw": baseline, "M1_code_neighbors": candidate},
        {"screen_authorized": True, "selected": "M1_code_neighbors"},
    )

    assert selected["confirmation_authorized"] is False
    assert selected["gates"]["no_task_regresses_by_more_than_one_seed"] is False


def test_confirmation_selector_requires_positive_clustered_present_result():
    selected = select_confirmation(
        {
            "M0_raw": _execution_run(CONFIRMATION_CELLS, candidate=False),
            "M1_code_neighbors": _execution_run(CONFIRMATION_CELLS, candidate=True),
        },
        {
            "retrieval_gates": {
                "mrr": True,
                "coverage": True,
                "latency": True,
            }
        },
        {"confirmation_authorized": True, "selected": "M1_code_neighbors"},
    )

    assert selected["selected"] == "M1_code_neighbors"
    assert selected["robustness_authorized"] is True
    assert selected["paired_cells"] == 102
    assert selected["task_clustered_bootstrap_95_ci"][0] > 0
    assert all(selected["gates"].values())


def test_robustness_selector_requires_every_condition_to_hold():
    artifacts = {}
    for index, condition in enumerate(CONDITIONS):
        baseline = _artifact("M0_raw", candidate=False)
        candidate = _artifact("M1_code_neighbors", candidate=True)
        namespace = f"condition-{index}"
        baseline["namespace"] = namespace
        candidate["namespace"] = namespace
        artifacts[(condition, "M0_raw")] = baseline
        artifacts[(condition, "M1_code_neighbors")] = candidate

    selected = select_robustness(
        artifacts,
        {"robustness_authorized": True, "selected": "M1_code_neighbors"},
    )

    assert selected["selected"] == "M1_code_neighbors"
    assert selected["raw_base_promoted"] is True
    assert all(value["passed"] for value in selected["conditions"].values())


def test_remaining_vps2_wrappers_freeze_concurrency_and_condition_order():
    root = Path(__file__).parents[1] / "scripts"
    screen = (root / "recall_code_aware_vps2_screen.sh").read_text(encoding="utf-8")
    confirmation = (root / "recall_code_aware_vps2_confirmation.sh").read_text(encoding="utf-8")
    robustness = (root / "recall_code_aware_vps2_robustness.sh").read_text(encoding="utf-8")
    broker = (root / "recall_code_aware_broker.sh").read_text(encoding="utf-8")

    assert "AMB_BLOCK_CONCURRENCY=3" in screen
    assert "--timeout 600" in screen
    assert "--price-in 0.0574" in screen
    assert "--price-out 0.1148" in screen
    assert "--price-as-of 2026-08-22" in screen
    assert 'AMB_PARTICIPANT_IMAGE_DIGEST="${AMB_PARTICIPANT_AGENT_DIGEST:' in screen
    assert 'AMB_CHECKER_IMAGE_DIGEST="sha256:${AMB_CHECKER_IMAGE_DIGEST}"' in screen
    assert "start_code_aware_broker" in screen
    assert "AMB_BLOCK_CONCURRENCY=3" in confirmation
    assert "--timeout 600" in confirmation
    assert "--price-in 0.0574" in confirmation
    assert "--price-out 0.1148" in confirmation
    assert "--price-as-of 2026-08-22" in confirmation
    assert 'AMB_PARTICIPANT_IMAGE_DIGEST="${AMB_PARTICIPANT_AGENT_DIGEST:' in confirmation
    assert 'AMB_CHECKER_IMAGE_DIGEST="sha256:${AMB_CHECKER_IMAGE_DIGEST}"' in confirmation
    assert "start_code_aware_broker" in confirmation
    assert "conditions=(present absent adjacent contradictory superseded)" in robustness
    assert "--captures 3" in robustness
    assert 'local broker_run_dir="$1" broker_artifact_id="$2"' in broker
    assert "--user 0:0" in broker
