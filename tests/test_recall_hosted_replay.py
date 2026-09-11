from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from adapters.recall_hosted.adapter import HostedHttpResponse
from harness.adapters.base import CorpusManifest
from scripts.recall_hosted_replay import run_replay, score_items


class FakeReplayClient:
    def __init__(self, variant: str = "A0_raw") -> None:
        self.variant = variant
        self.calls = []

    def request(self, path, payload=None):
        self.calls.append((path, payload))
        if path == "/version":
            return {"product": "RE-call Hosted 1.0", "variant": self.variant}
        if path == "/v1/add":
            return {
                "success": True,
                "request_id": payload["request_id"],
                "user_id": payload["user_id"],
                "session_id": payload["session_id"],
                "compiler_fallback": False,
            }
        if path == "/v1/search":
            return {
                "data": [
                    {"id": "one", "content": "the private governing phrase appears here"},
                    {"id": "two", "content": "second stored item"},
                ]
            }
        return {"status": "deleted"}

    def request_with_headers(self, path, payload=None):
        response = self.request(path, payload)
        return HostedHttpResponse(
            response,
            {
                "x-recall-facet-fallback": "1",
                "x-recall-reranker-fallback": "1",
            },
        )


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


def test_replay_refuses_missing_search_fallback_telemetry(tmp_path):
    """RED: interpreting absent headers as false silently under-counted degraded requests."""
    corpus, task = _fixture(tmp_path)
    client = FakeReplayClient()
    client.request_with_headers = lambda path, payload=None: HostedHttpResponse(
        client.request(path, payload), {}
    )

    with pytest.raises(RuntimeError, match="fallback telemetry"):
        run_replay(
            client,
            variant_name="A0_raw",
            corpus=corpus,
            tasks=[task],
            namespace="replay-a0",
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
            {"id": "noise", "content": "unrelated"},
            {"id": "partial", "content": "alpha evidence"},
            {"id": "complete", "content": "beta evidence"},
        ],
        ("alpha", "beta"),
    )

    assert metrics == {
        "hit_at_1": False,
        "hit_at_5": True,
        "hit_at_10": True,
        "hit_in_returned_budget": True,
        "complete_coverage": True,
        "reciprocal_rank": 0.5,
        "item_count": 3,
        "character_count": 36,
    }
    incomplete = score_items([{"id": "partial", "content": "alpha only"}], ("alpha", "beta"))
    assert incomplete["complete_coverage"] is False
