from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from adapters.recall_hosted.adapter import HostedHttpResponse
from harness.adapters.base import CorpusManifest
from scripts.recall_hosted_replay import _percentile, run_replay, score_items


class FakeReplayClient:
    def __init__(self, variant: str = "A0_raw") -> None:
        self.variant = variant
        self.calls = []

    def request(self, path, payload=None):
        self.calls.append((path, payload))
        if path == "/version":
            return {
                "product": "RE-call Hosted 1.0",
                "variant": self.variant,
                "git_commit": "abc123",
                "embedding_profile": "voyage-context-4-v1",
                "reranker_provider": "voyage",
                "reranker_model": "rerank-2.5",
                "candidate_width": 100,
                "rrf_constant": 60,
            }
        if path == "/v1/add":
            return {
                "success": True,
                "request_id": payload["request_id"],
                "user_id": payload["user_id"],
                "session_id": payload["session_id"],
                "compiler_fallback": False,
            }
        if path == "/v1/sparse/backfill":
            return {"status": "ready", "sparse_chunk_count": 1}
        if path == "/v1/corpus/status":
            return {
                "status": "ready",
                "chunk_count": 1,
                "raw_chunk_count": 1,
                "compiled_chunk_count": 0,
                "source_session_count": 1,
                "authored_relation_count": 0,
                "eligible_relation_count": 0,
                "store_relation_count": 0,
                "generation_id": "aml-clean-reranker-v1",
                "corpus_sha256": "a" * 64,
                "variant": self.variant,
                "served_commit": "abc123",
            }
        if path == "/v1/search":
            return {
                "data": [
                    {
                        "id": "one",
                        "content": "the private governing phrase appears here",
                        "session_id": "sessions/task/p01.jsonl",
                    },
                    {
                        "id": "two",
                        "content": "second stored item",
                        "session_id": "sessions/task/p01.jsonl",
                    },
                ]
            }
        return {"status": "deleted"}

    def request_with_headers(self, path, payload=None):
        response = self.request(path, payload)
        clean = self.variant in {"B0_raw", "B1_raw_rerank"}
        reranked = self.variant == "B1_raw_rerank"
        headers = {
            "x-recall-facet-fallback": "1" if not clean else "0",
            "x-recall-reranker-fallback": "1" if not clean else "0",
            "x-recall-task-type": "bugfix" if not clean else "unknown",
        }
        if clean:
            headers.update(
                {
                    "x-recall-reranker-attempted": str(int(reranked)),
                    "x-recall-reranker-completed": str(int(reranked)),
                    "x-recall-reranker-provider": "voyage" if reranked else "none",
                    "x-recall-reranker-model": "rerank-2.5" if reranked else "none",
                    "x-recall-reranker-input-count": "2",
                    "x-recall-reranker-output-count": "2",
                    "x-recall-reranker-permutation-valid": "1",
                    "x-recall-reranker-top10-order-changed": str(int(reranked)),
                    "x-recall-reranker-top10-membership-changed": "0",
                    "x-recall-reranker-top100-order-changed": str(int(reranked)),
                    "x-recall-reranker-top100-membership-changed": "0",
                    "x-recall-reranker-ms": "5.0" if reranked else "0.0",
                    "x-recall-search-ms": "10.0",
                    "x-recall-reranker-candidate-chars": "100",
                    "x-recall-reranker-estimated-cost-usd": ("0.000001" if reranked else "0"),
                    "x-recall-served-commit": "abc123",
                    "x-recall-generation": "aml-clean-reranker-v1",
                    "x-recall-corpus-sha256": "a" * 64,
                    "x-recall-variant": self.variant,
                }
            )
        return HostedHttpResponse(
            response,
            headers,
        )


def test_replay_p95_uses_nearest_rank_for_sixteen_requests():
    """RED: floor indexing reported the second slowest request as p95."""
    assert _percentile(list(range(1, 17)), 0.95) == 16


def _fixture(tmp_path):
    relative = "sessions/task/p01.jsonl"
    session = tmp_path / relative
    session.parent.mkdir(parents=True)
    session.write_text(
        json.dumps({"role": "user", "content": "stored history", "ts": "2026-01-01T00:00:00Z"})
        + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(session.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"sessions": {relative: digest}}), encoding="utf-8"
    )
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.json").write_text("{}", encoding="utf-8")
    task = SimpleNamespace(
        task_id="task",
        prompt="exact task prompt",
        kind="primary",
        fact_terms=("private governing phrase",),
        path=task_dir,
    )
    return CorpusManifest(tmp_path, {relative: digest}), task


def test_replay_never_sends_fact_terms_to_the_memory_system(tmp_path):
    """The scorer may read labels only after Search; leaking them into `query` makes this RED."""
    corpus, task = _fixture(tmp_path)
    client = FakeReplayClient()

    result = run_replay(
        client,
        variant_name="A0_raw",
        corpus=corpus,
        tasks=[task],
        namespace="replay-a0",
    )

    search_payload = next(payload for path, payload in client.calls if path == "/v1/search")
    assert search_payload == {"query": "exact task prompt", "user_id": "replay-a0", "top_k": 100}
    assert result["rows"][0]["metrics"]["complete_coverage"] is True


def test_replay_reuses_frozen_dense_corpus_and_backfills_only_sparse(tmp_path):
    corpus, task = _fixture(tmp_path)
    client = FakeReplayClient("C1_splade")
    sparse_client = FakeReplayClient("C1_splade")

    result = run_replay(
        client,
        variant_name="C1_splade",
        corpus=corpus,
        tasks=[task],
        namespace="shared-raw-corpus",
        reuse_corpus=True,
        sparse_backfill_client=sparse_client,
    )

    paths = [path for path, _ in client.calls]
    assert paths[:1] == ["/version"]
    assert sparse_client.calls == [("/v1/sparse/backfill", {"user_id": "shared-raw-corpus"})]
    assert "/v1/delete" not in paths
    assert "/v1/add" not in paths
    assert result["corpus_reused"] is True
    assert result["dense_embedding_pass"] is False
    assert result["sparse_backfill_timeout_seconds"] == 7_200.0
    assert result["messages_offered"] == 1
    assert result["aggregate"]["add_p50_ms"] is None


def test_clean_reranker_replay_reuses_exact_corpus_and_captures_three_times(tmp_path):
    corpus, task = _fixture(tmp_path)
    client = FakeReplayClient("B1_raw_rerank")

    result = run_replay(
        client,
        variant_name="B1_raw_rerank",
        corpus=corpus,
        tasks=[task],
        namespace="clean-present",
        reuse_corpus=True,
        captures=3,
        expected_corpus_sha256="a" * 64,
    )

    paths = [path for path, _ in client.calls]
    assert "/v1/delete" not in paths
    assert "/v1/add" not in paths
    assert paths.count("/v1/search") == 3
    assert result["task_count"] == 1
    assert result["capture_count"] == 3
    assert result["request_count"] == 3
    assert result["corpus_reused"] is True
    assert result["dense_embedding_pass"] is False
    assert result["corpus_status"]["corpus_sha256"] == "a" * 64
    assert result["aggregate"]["reranker_attempts"] == 3
    assert result["aggregate"]["reranker_completions"] == 3
    assert result["aggregate"]["reranker_fallbacks"] == 0
    assert result["aggregate"]["invalid_permutations"] == 0
    assert {(row["task_id"], row["capture"]) for row in result["rows"]} == {
        ("task", 0),
        ("task", 1),
        ("task", 2),
    }


def test_replay_resumes_partial_ingest_without_delete_or_dense_reembedding(tmp_path):
    corpus, task = _fixture(tmp_path)
    client = FakeReplayClient("C2_procedure")

    result = run_replay(
        client,
        variant_name="C2_procedure",
        corpus=corpus,
        tasks=[task],
        namespace="shared-procedure-corpus",
        resume_ingest=True,
    )

    paths = [path for path, _ in client.calls]
    assert paths[:2] == ["/version", "/v1/add"]
    assert "/v1/delete" not in paths
    assert result["ingest_resumed"] is True
    assert result["dense_embedding_pass"] is True


def test_replay_refuses_incompatible_resume_and_cache_reuse(tmp_path):
    corpus, task = _fixture(tmp_path)

    with pytest.raises(ValueError, match="resume ingest"):
        run_replay(
            FakeReplayClient("C2_procedure"),
            variant_name="C2_procedure",
            corpus=corpus,
            tasks=[task],
            namespace="shared-procedure-corpus",
            reuse_corpus=True,
            resume_ingest=True,
        )


def test_replay_refuses_to_reuse_an_empty_corpus(tmp_path):
    corpus, task = _fixture(tmp_path)
    client = FakeReplayClient("C1_splade")
    original_request = client.request

    def empty_backfill(path, payload=None):
        if path == "/v1/sparse/backfill":
            client.calls.append((path, payload))
            return {"status": "ready", "sparse_chunk_count": 0}
        return original_request(path, payload)

    client.request = empty_backfill

    with pytest.raises(RuntimeError, match="did not prove corpus readiness"):
        run_replay(
            client,
            variant_name="C1_splade",
            corpus=corpus,
            tasks=[task],
            namespace="empty-corpus",
            reuse_corpus=True,
        )


def test_replay_counts_request_local_search_fallback_headers(tmp_path):
    """Hard-coding replay fallback counts to zero makes this request exercise turn RED."""
    corpus, task = _fixture(tmp_path)
    result = run_replay(
        FakeReplayClient(),
        variant_name="A0_raw",
        corpus=corpus,
        tasks=[task],
        namespace="replay-a0",
    )

    assert result["aggregate"]["facet_fallbacks"] == 1
    assert result["aggregate"]["reranker_fallbacks"] == 1
    assert result["rows"][0]["facet_fallback"] is True
    assert result["rows"][0]["reranker_fallback"] is True
    assert result["rows"][0]["task_type"] == "bugfix"
    assert result["routing_aggregate"]["bugfix"]["task_count"] == 1


def test_replay_refuses_missing_search_fallback_telemetry(tmp_path):
    """RED: interpreting absent headers as false silently under-counted degraded requests."""
    corpus, task = _fixture(tmp_path)
    client = FakeReplayClient()
    client.request_with_headers = lambda path, payload=None: HostedHttpResponse(
        client.request(path, payload), {"x-recall-task-type": "unknown"}
    )

    with pytest.raises(RuntimeError, match="fallback telemetry"):
        run_replay(
            client,
            variant_name="A0_raw",
            corpus=corpus,
            tasks=[task],
            namespace="replay-a0",
        )


def test_replay_refuses_missing_task_routing_telemetry(tmp_path):
    corpus, task = _fixture(tmp_path)
    client = FakeReplayClient("C4_task_pack")
    client.request_with_headers = lambda path, payload=None: HostedHttpResponse(
        client.request(path, payload),
        {
            "x-recall-facet-fallback": "0",
            "x-recall-reranker-fallback": "0",
        },
    )

    with pytest.raises(RuntimeError, match="task routing telemetry"):
        run_replay(
            client,
            variant_name="C4_task_pack",
            corpus=corpus,
            tasks=[task],
            namespace="replay-c4",
        )


def test_replay_refuses_wrong_served_variant_before_mutating_corpus(tmp_path):
    """Removing the `/version` equality gate makes this test fail its refusal assertion."""
    corpus, task = _fixture(tmp_path)
    client = FakeReplayClient("A4_pack_7000")

    with pytest.raises(RuntimeError, match="variant mismatch"):
        run_replay(
            client,
            variant_name="A0_raw",
            corpus=corpus,
            tasks=[task],
            namespace="replay-a0",
        )

    assert client.calls == [("/version", None)]


def test_replay_scoring_reports_rank_coverage_and_context_size():
    """A first-hit rank mutation or any-term complete coverage mutation makes this test RED."""
    metrics = score_items(
        [
            {"id": "noise", "content": "unrelated", "session_id": "noise"},
            {"id": "partial", "content": "alpha evidence", "session_id": "p01"},
            {"id": "complete", "content": "beta evidence", "session_id": "p02"},
        ],
        ("alpha", "beta"),
        relevant_sources=("p01", "p02"),
    )

    assert metrics == {
        "hit_at_1": False,
        "hit_at_5": True,
        "hit_at_10": True,
        "hit_at_100": True,
        "hit_in_returned_budget": True,
        "complete_coverage_at_5": True,
        "complete_coverage_at_10": True,
        "complete_coverage_at_100": True,
        "complete_coverage": True,
        "reciprocal_rank": 0.5,
        "source_session_recall": 1.0,
        "duplicate_session_concentration": 0.0,
        "item_count": 3,
        "character_count": 36,
    }
    incomplete = score_items(
        [{"id": "partial", "content": "alpha only", "session_id": "p01"}],
        ("alpha", "beta"),
    )
    assert incomplete["complete_coverage"] is False


def test_replay_scoring_reports_duplicate_session_concentration():
    metrics = score_items(
        [
            {"id": "one", "content": "alpha", "session_id": "p01"},
            {"id": "two", "content": "more alpha", "session_id": "p01"},
            {"id": "three", "content": "beta", "session_id": "p02"},
            {"id": "four", "content": "noise", "session_id": "noise"},
        ],
        ("alpha", "beta"),
        relevant_sources=("p01", "p02", "p03"),
    )

    assert metrics["source_session_recall"] == pytest.approx(2 / 3)
    assert metrics["duplicate_session_concentration"] == 0.25
