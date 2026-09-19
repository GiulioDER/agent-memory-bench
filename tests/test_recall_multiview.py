from __future__ import annotations

import copy

import pytest

from scripts.recall_multiview_select import VIEW_KINDS, select_multiview


def _aggregate(*, mrr: float, coverage_10: float) -> dict[str, float | int]:
    return {
        "mean_reciprocal_rank": mrr,
        "complete_coverage_at_10": coverage_10,
        "complete_coverage_at_100": 1.0,
        "mean_source_session_recall": 1.0,
        "mean_character_count": 1_000.0,
        "search_p95_ms": 100.0,
        "compiler_fallbacks": 0,
    }


def _artifact(variant: str) -> dict:
    kinds = sorted(VIEW_KINDS[variant])
    candidate = bool(kinds)
    returned_kind = kinds[0] if candidate else "raw"
    rows = [
        {
            "task_id": f"task-{task:02d}",
            "capture": capture,
            "kind": "primary",
            "query_sha256": f"query-{task:02d}",
            "fact_terms_sha256": f"facts-{task:02d}",
            "items": [
                {
                    "id": f"{task}-{capture}",
                    "content": "evidence",
                    "session_id": "sessions/source.jsonl",
                    "kind": returned_kind,
                }
            ],
        }
        for task in range(34)
        for capture in range(3)
    ]
    compiled_count = 196 if candidate else 0
    return {
        "schema_version": 5,
        "variant": variant,
        "namespace": "multiview-present",
        "version": {
            "variant": variant,
            "git_commit": "abc123",
            "embedding_profile": "voyage-context-4-v1",
            "candidate_width": 100,
            "rrf_constant": 60,
            "anchor_compiler_prompt_digest": "prompt-sha",
            "compiled_kinds": kinds,
            "drop_compiler_fallback": candidate,
        },
        "corpus_manifest_sha256": "manifest-sha",
        "task_set_sha256": "task-sha",
        "sessions_offered": 196,
        "messages_offered": 500,
        "add_request_count": 196,
        "task_count": 34,
        "capture_count": 3,
        "request_count": 102,
        "http_timeout_seconds": 180.0,
        "dense_embedding_pass": True,
        "corpus_reused": False,
        "corpus_status": {
            "status": "ready",
            "chunk_count": 392 if candidate else 196,
            "raw_chunk_count": 196,
            "compiled_chunk_count": compiled_count,
            "raw_corpus_sha256": "a" * 64,
            "compiled_corpus_sha256": "b" * 64,
            "compiled_kind_counts": {returned_kind: compiled_count} if candidate else {},
            "compiler_profile_counts": {"anchor-v2": compiled_count} if candidate else {},
        },
        "aggregate": _aggregate(
            mrr=0.6 if candidate else 0.5,
            coverage_10=0.8 if candidate else 0.7,
        ),
        "rows": rows,
    }


def _admission() -> dict:
    return {
        "schema_version": 1,
        "selected_compiler": "V2_anchor_raw",
        "admission_pass": True,
        "authorize_m2_m3_retrieval": True,
    }


def test_multiview_selector_promotes_views_only_to_executable_preregistration():
    artifacts = {
        variant: _artifact(variant)
        for variant in ("M0_multiview_raw", "M2_repository_raw", "M3_experience_raw")
    }

    result = select_multiview(artifacts, _admission())

    assert result["retrieval_preregistration_candidates"] == [
        "M2_repository_raw",
        "M3_experience_raw",
    ]
    assert result["authorize_executable_run"] is False
    assert result["dense_embedding_passes"] == 3
    assert all(
        candidate["activated_task_count"] == 34 for candidate in result["candidates"].values()
    )


def test_multiview_selector_refuses_cross_view_records():
    artifacts = {
        variant: _artifact(variant)
        for variant in ("M0_multiview_raw", "M2_repository_raw", "M3_experience_raw")
    }
    artifacts["M2_repository_raw"]["rows"][0]["items"][0]["kind"] = "procedure"

    with pytest.raises(ValueError, match="cross-view Search item"):
        select_multiview(artifacts, _admission())


def test_multiview_selector_refuses_to_bypass_compiler_admission():
    artifacts = {
        variant: _artifact(variant)
        for variant in ("M0_multiview_raw", "M2_repository_raw", "M3_experience_raw")
    }
    admission = copy.deepcopy(_admission())
    admission["admission_pass"] = False

    with pytest.raises(ValueError, match="admission did not pass"):
        select_multiview(artifacts, admission)
