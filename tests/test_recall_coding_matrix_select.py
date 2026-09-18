from __future__ import annotations

import copy

import pytest

from scripts.recall_coding_matrix_select import select_coding_matrix
from scripts.recall_hosted_replay import CODING_MATRIX_VARIANTS


def _artifact(name: str, index: int) -> dict:
    metrics = {
        "C0_raw_lexical": (0.40, 0.70, 0.70, 0.30, 10_000, 100),
        "C1_splade": (0.43, 0.72, 0.72, 0.31, 10_200, 250),
        "C2_procedure": (0.44, 0.73, 0.73, 0.34, 10_500, 270),
        "C3_rerank": (0.46, 0.73, 0.73, 0.38, 10_500, 290),
        "C4_task_pack": (0.46, 0.73, 0.73, 0.39, 7_000, 295),
    }[name]
    complete10, complete100, complete, mrr, characters, p95 = metrics
    return {
        "schema_version": 1,
        "variant": name,
        "version": {
            "product": "RE-call Hosted 1.0",
            "git_commit": "commit",
            "embedding_profile": "voyage-context-4-v1",
            "sparse_revision": "pinned",
            "variant": name,
        },
        "corpus_manifest_sha256": "corpus",
        "task_set_sha256": "tasks",
        "task_count": 1,
        "sessions_offered": 2,
        "messages_offered": 3,
        "http_timeout_seconds": 180.0,
        "sparse_backfill_timeout_seconds": (
            7_200.0 if name in {"C1_splade", "C3_rerank", "C4_task_pack"} else None
        ),
        "corpus_reused": name in {"C1_splade", "C3_rerank", "C4_task_pack"},
        "dense_embedding_pass": name in {"C0_raw_lexical", "C2_procedure"},
        "aggregate": {
            "complete_coverage_at_10": complete10,
            "complete_coverage_at_100": complete100,
            "complete_coverage": complete,
            "mean_reciprocal_rank": mrr,
            "mean_character_count": characters,
            "search_p95_ms": p95,
            "sparse_failures": 0,
        },
        "rows": [
            {
                "task_id": "task",
                "kind": "primary",
                "query_sha256": "query",
                "fact_terms_sha256": "facts",
                "task_type": "bugfix" if index == 4 else "unknown",
            }
        ],
    }


def _artifacts() -> list[dict]:
    return [_artifact(name, index) for index, name in enumerate(CODING_MATRIX_VARIANTS)]


def test_selector_applies_every_incremental_retrieval_gate_in_order():
    selected = select_coding_matrix(_artifacts())

    assert selected["gates"] == {
        "C1_splade": True,
        "C2_procedure": True,
        "C3_rerank": True,
        "C4_task_pack": True,
    }
    assert selected["deepest_retrieval_eligible"] == "C4_task_pack"
    assert selected["deltas"]["c4_character_reduction"] == pytest.approx(1 / 3)


def test_selector_stops_at_first_failed_incremental_gate():
    artifacts = _artifacts()
    artifacts[2]["aggregate"]["mean_reciprocal_rank"] = 0.31

    selected = select_coding_matrix(artifacts)

    assert selected["gates"]["C2_procedure"] is False
    assert selected["deepest_retrieval_eligible"] == "C1_splade"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda items: items.pop(), "exactly one C0 through C4"),
        (
            lambda items: items[4]["version"].__setitem__("git_commit", "drift"),
            "product identity drift",
        ),
        (
            lambda items: items[3]["rows"][0].__setitem__("query_sha256", "drift"),
            "task identity drift",
        ),
        (
            lambda items: items[1]["aggregate"].__setitem__("sparse_failures", 1),
            "learned sparse failure",
        ),
        (
            lambda items: items[3].__setitem__("dense_embedding_pass", True),
            "invalid corpus cache lineage",
        ),
        (
            lambda items: items[1].__setitem__("sparse_backfill_timeout_seconds", 180.0),
            "invalid sparse backfill timeout identity",
        ),
    ],
)
def test_selector_refuses_invalid_or_unpaired_artifacts(mutation, message):
    artifacts = copy.deepcopy(_artifacts())
    mutation(artifacts)

    with pytest.raises(ValueError, match=message):
        select_coding_matrix(artifacts)
