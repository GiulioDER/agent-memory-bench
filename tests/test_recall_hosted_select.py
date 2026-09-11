from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.recall_hosted_replay import REGISTERED_VARIANTS
from scripts.recall_hosted_select import select_replay


def _artifacts() -> list[dict]:
    coverages = {
        "A0_raw": 0.60,
        "A1_compiler": 0.70,
        "A2_facets": 0.75,
        "A3_rerank": 0.78,
        "A4_pack_5000": 0.796,
        "A4_pack_7000": 0.800,
        "A4_pack_9000": 0.805,
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
            "task_count": 34,
            "sessions_offered": 10,
            "messages_offered": 100,
            "aggregate": {
                "complete_coverage": coverages[name],
                "hit_at_1": 0.5,
                "mean_reciprocal_rank": 0.6,
                "mean_character_count": 4_000,
                "add_p95_ms": 1_000,
                "search_p95_ms": 500,
                "compiler_fallbacks": 0,
                "facet_fallbacks": 0,
                "reranker_fallbacks": 0,
            },
        }
        for name in REGISTERED_VARIANTS
    ]


def test_selector_chooses_smallest_a4_arm_within_one_absolute_point():
    """RED: choosing only the maximum coverage arm returned 9,000 instead of 5,000."""
    result = select_replay(_artifacts())
    assert result["baseline"] == "A0_raw"
    assert result["candidate"] == "A4_pack_5000"
    assert result["candidate_context_chars"] == 5_000


def test_selector_refuses_population_or_product_identity_drift():
    """RED: skipping identity comparison accepted a different prompt in one arm."""
    population_drift = _artifacts()
    population_drift[3]["task_set_sha256"] = "different"
    with pytest.raises(ValueError, match="population drift"):
        select_replay(population_drift)

    identity_drift = _artifacts()
    identity_drift[4]["version"]["facet_prompt_digest"] = "different"
    with pytest.raises(ValueError, match="product identity drift"):
        select_replay(identity_drift)


def test_selector_requires_exactly_one_artifact_per_registered_variant():
    missing = _artifacts()[:-1]
    with pytest.raises(ValueError, match="exactly one"):
        select_replay(missing)

    duplicate = deepcopy(_artifacts())
    duplicate[-1]["variant"] = duplicate[0]["variant"]
    with pytest.raises(ValueError, match="exactly one"):
        select_replay(duplicate)
