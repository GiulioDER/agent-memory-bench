from __future__ import annotations

import importlib
import importlib.util
from copy import deepcopy

import pytest


def _artifacts() -> tuple[dict, dict, dict]:
    common_version = {
        "product": "RE-call Hosted 1.0",
        "git_commit": "a" * 40,
        "compiler_prompt_digest": "offset",
        "anchor_compiler_prompt_digest": "anchor",
        "facet_prompt_digest": "facet",
        "embedding_profile": "voyage-context-4-v1",
    }
    common = {
        "corpus_manifest_sha256": "c" * 64,
        "task_set_sha256": "t" * 64,
        "task_count": 2,
        "sessions_offered": 10,
        "messages_offered": 100,
        "add_request_count": 10,
        "http_timeout_seconds": 180.0,
        "rows": [
            {
                "task_id": "one",
                "kind": "primary",
                "query_sha256": "q1",
                "fact_terms_sha256": "f1",
            },
            {
                "task_id": "two",
                "kind": "primary",
                "query_sha256": "q2",
                "fact_terms_sha256": "f2",
            },
        ],
    }
    baseline = {
        **deepcopy(common),
        "schema_version": 4,
        "variant": "V2_raw",
        "version": {**common_version, "variant": "V2_raw"},
        "aggregate": {
            "complete_coverage_at_100": 0.95,
            "mean_reciprocal_rank": 0.32,
            "compiler_fallbacks": 0,
        },
    }
    candidate = {
        **deepcopy(common),
        "schema_version": 4,
        "variant": "V2_anchor_raw",
        "version": {**common_version, "variant": "V2_anchor_raw"},
        "typed_session_count": 9,
        "typed_add_count": 9,
        "full_session_fallback_count": 0,
        "compiled_record_count": 18,
        "corpus_status": {
            "raw_chunk_count": 100,
            "compiled_chunk_count": 18,
            "source_session_count": 10,
        },
        "aggregate": {
            "complete_coverage_at_100": 0.95,
            "mean_reciprocal_rank": 0.33,
            "compiler_fallbacks": 0,
        },
    }
    audit = {
        "schema_version": 1,
        "corpus_manifest_sha256": "c" * 64,
        "eligible_session_count": 10,
        "compiled_session_count": 9,
        "fallback_session_count": 0,
        "raw_session_count": 10,
        "session_without_compiled_record_count": 1,
        "session_without_raw_record_count": 0,
        "audited_record_count": 18,
        "unsupported_claim_count": 0,
        "invalid_span_count": 0,
        "wrong_profile_count": 0,
        "violations": [],
    }
    return baseline, candidate, audit


def _selector():
    spec = importlib.util.find_spec("scripts.recall_anchor_compiler_select")
    assert spec is not None, "compiler v2 needs a frozen mechanical admission selector"
    return importlib.import_module("scripts.recall_anchor_compiler_select").select_anchor_compiler


def test_anchor_selector_authorizes_views_only_when_every_admission_gate_passes():
    """RED on pre-fix: no compiler v2 admission selector existed."""
    baseline, candidate, audit = _artifacts()

    result = _selector()(baseline, candidate, audit)

    assert result["admission_pass"] is True
    assert result["selected_compiler"] == "V2_anchor_raw"
    assert result["authorize_m2_m3_retrieval"] is True
    assert result["accepted_typed_session_rate"] == 0.9
    assert result["full_session_fallback_rate"] == 0.0
    assert all(result["gates"].values())


def test_anchor_selector_accepts_the_explicit_v3_identity_without_relaxing_gates():
    """Mutation proof: restoring either hardcoded v2 identity leaves the result empty."""
    baseline, candidate, audit = _artifacts()
    baseline["variant"] = "V3_raw"
    baseline["version"]["variant"] = "V3_raw"
    candidate["variant"] = "V3_anchor_raw"
    candidate["version"]["variant"] = "V3_anchor_raw"

    try:
        result = _selector()(
            baseline,
            candidate,
            audit,
            baseline_variant="V3_raw",
            candidate_variant="V3_anchor_raw",
        )
    except (TypeError, ValueError):
        result = {}

    assert result.get("admission_pass") is True
    assert result.get("selected_compiler") == "V3_anchor_raw"
    assert all(result.get("gates", {}).values())


@pytest.mark.parametrize(
    ("mutation", "failed_gate"),
    [
        (lambda c, a: c.update(typed_session_count=8), "typed_session_acceptance"),
        (lambda c, a: c.update(full_session_fallback_count=1), "full_session_fallback"),
        (lambda c, a: a.update(unsupported_claim_count=1), "source_grounding"),
        (lambda c, a: c["aggregate"].update(complete_coverage_at_100=0.94), "rank_100"),
    ],
)
def test_anchor_selector_stops_on_each_frozen_gate(mutation, failed_gate):
    baseline, candidate, audit = _artifacts()
    mutation(candidate, audit)
    if failed_gate == "typed_session_acceptance":
        candidate["typed_add_count"] = candidate["typed_session_count"]
        audit["compiled_session_count"] = candidate["typed_session_count"]
        audit["session_without_compiled_record_count"] = (
            audit["eligible_session_count"] - audit["compiled_session_count"]
        )
    if failed_gate == "full_session_fallback":
        candidate["aggregate"]["compiler_fallbacks"] = candidate[
            "full_session_fallback_count"
        ]
        audit["fallback_session_count"] = candidate["full_session_fallback_count"]

    result = _selector()(baseline, candidate, audit)

    assert result["admission_pass"] is False
    assert result["selected_compiler"] == "V2_raw"
    assert result["authorize_m2_m3_retrieval"] is False
    assert result["gates"][failed_gate] is False


def test_anchor_selector_refuses_population_or_audit_identity_drift():
    baseline, candidate, audit = _artifacts()
    candidate["messages_offered"] += 1
    with pytest.raises(ValueError, match="population drift"):
        _selector()(baseline, candidate, audit)

    baseline, candidate, audit = _artifacts()
    audit["corpus_manifest_sha256"] = "different"
    with pytest.raises(ValueError, match="audit corpus drift"):
        _selector()(baseline, candidate, audit)


def test_anchor_selector_refuses_replay_or_stored_corpus_counter_drift():
    """RED: replay and stored counter mismatches did not stop admission."""
    baseline, candidate, audit = _artifacts()
    audit["fallback_session_count"] = 1
    candidate["full_session_fallback_count"] = 1
    candidate["aggregate"]["compiler_fallbacks"] = 0
    with pytest.raises(ValueError, match="fallback counter drift"):
        _selector()(baseline, candidate, audit)

    baseline, candidate, audit = _artifacts()
    candidate["corpus_status"]["compiled_chunk_count"] = 17
    with pytest.raises(ValueError, match="stored compiler counter drift"):
        _selector()(baseline, candidate, audit)
