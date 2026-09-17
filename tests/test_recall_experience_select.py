from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.recall_experience_select import select_experience
from scripts.recall_hosted_replay import EXPERIENCE_VARIANTS


def _artifacts(
    *,
    coverages: tuple[float, float, float] = (0.70, 0.70, 0.80),
    reciprocal_ranks: tuple[float, float, float] = (0.50, 0.60, 0.60),
) -> list[dict]:
    row_coverage = {
        "E0_raw": (True, True, False, False),
        "E1_compiled": (True, False, True, False),
        "E2_compiled_raw": (True, True, True, False),
    }
    return [
        {
            "schema_version": 1,
            "variant": name,
            "version": {
                "product": "RE-call Hosted 1.0",
                "git_commit": "a" * 40,
                "compiler_prompt_digest": "compiler",
                "facet_prompt_digest": "facet",
                "variant": name,
            },
            "corpus_manifest_sha256": "corpus",
            "task_set_sha256": "tasks",
            "task_count": 4,
            "sessions_offered": 10,
            "messages_offered": 100,
            "aggregate": {
                "complete_coverage_at_10": coverages[index],
                "mean_reciprocal_rank": reciprocal_ranks[index],
                "mean_character_count": 4_000 - 500 * index,
                "add_p95_ms": 1_000,
                "search_p95_ms": 500,
                "compiler_fallbacks": 0,
            },
            "rows": [
                {
                    "task_id": f"task-{task_index}",
                    "kind": "primary",
                    "query_sha256": f"query-{task_index}",
                    "fact_terms_sha256": f"facts-{task_index}",
                    "metrics": {"complete_coverage_at_10": complete},
                }
                for task_index, complete in enumerate(row_coverage[name])
            ],
        }
        for index, name in enumerate(EXPERIENCE_VARIANTS)
    ]


def test_selector_promotes_compiled_plus_raw_when_it_recovers_compiler_losses():
    result = select_experience(_artifacts())

    assert result["e1_pass"] is True
    assert result["e2_pass"] is True
    assert result["e1_lost_task_count"] == 1
    assert result["e2_recovered_task_count"] == 1
    assert result["e2_recovery_rate"] == 1.0
    assert result["candidate"] == "E2_compiled_raw"


def test_selector_falls_back_to_raw_when_compiled_arms_miss_the_registered_gates():
    artifacts = _artifacts(
        coverages=(0.70, 0.60, 0.65),
        reciprocal_ranks=(0.50, 0.49, 0.49),
    )

    result = select_experience(artifacts)

    assert result["e1_pass"] is False
    assert result["e2_pass"] is False
    assert result["candidate"] == "E0_raw"


def test_selector_refuses_population_product_or_task_identity_drift():
    population_drift = _artifacts()
    population_drift[1]["messages_offered"] = 101
    with pytest.raises(ValueError, match="population drift"):
        select_experience(population_drift)

    product_drift = _artifacts()
    product_drift[2]["version"]["compiler_prompt_digest"] = "different"
    with pytest.raises(ValueError, match="product identity drift"):
        select_experience(product_drift)

    task_drift = _artifacts()
    task_drift[1]["rows"][0]["query_sha256"] = "different"
    with pytest.raises(ValueError, match="task identity drift"):
        select_experience(task_drift)


def test_selector_requires_one_artifact_for_each_experience_arm():
    with pytest.raises(ValueError, match="exactly one"):
        select_experience(_artifacts()[:-1])

    duplicate = deepcopy(_artifacts())
    duplicate[-1]["variant"] = duplicate[0]["variant"]
    with pytest.raises(ValueError, match="exactly one"):
        select_experience(duplicate)
