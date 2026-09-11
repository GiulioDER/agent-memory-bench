from __future__ import annotations

import hashlib
import json

import pytest

from adapters.recall_hosted import mcp_bridge
from adapters.recall_hosted.adapter import RecallHostedAdapter, session_messages
from harness.adapters.base import CorpusManifest


class FakeClient:
    def __init__(self):
        self.calls = []

    def request(self, path, payload=None):
        self.calls.append((path, payload))
        if path == "/v1/add":
            return {
                "success": True,
                "request_id": payload["request_id"],
                "user_id": payload["user_id"],
                "session_id": payload["session_id"],
            }
        if path == "/v1/search":
            return {
                "data": [
                    {"session_id": "sessions/task/p01.jsonl", "score": 0.9},
                    {"session_id": "sessions/task/p01.jsonl", "score": 0.8},
                    {"session_id": "distractors/d01.jsonl", "score": 0.7},
                ]
            }
        return {"status": "deleted", "deleted_count": 0}


def test_session_translation_preserves_timestamp_and_tool_evidence(tmp_path):
    """`session_messages` was RED: pre-fix output kept ISO text instead of AML milliseconds."""
    path = tmp_path / "session.jsonl"
    path.write_text(
        json.dumps(
            {
                "role": "assistant",
                "content": "",
                "tool_name": "Bash",
                "tool_input": '{"command":"pytest"}',
                "tool_result": "1 failed",
                "ts": "2026-01-01T01:02:03Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    messages = session_messages(path)
    assert messages == [
        {
            "role": "assistant",
            "content": 'tool_name: Bash\ntool_input: {"command":"pytest"}\ntool_result: 1 failed',
            "timestamp": 1_767_229_323_000,
        }
    ]


def test_adapter_uses_public_add_search_and_builds_read_only_mcp(monkeypatch, tmp_path):
    relative = "sessions/task/p01.jsonl"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    source.write_text(
        '{"role":"user","content":"exact Error42","ts":"2026-01-01T00:00:00Z"}\n',
        encoding="utf-8",
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    corpus = CorpusManifest(tmp_path, {relative: digest})
    base = tmp_path / "base.md"
    base.write_text("base", encoding="utf-8")
    adapter = RecallHostedAdapter(tmp_path / "stage", base)
    client = FakeClient()
    monkeypatch.setattr(adapter, "_client", lambda **kwargs: client)

    report = adapter.ingest(corpus, "run-1")
    ranked = adapter.search("run-1", "Error42", limit=2)

    assert report.sessions_offered == 1
    assert report.items_stored == 1
    assert client.calls[0] == ("/v1/delete", {"user_id": "run-1"})
    assert client.calls[1][0] == "/v1/add"
    assert client.calls[1][1]["session_id"] == relative
    assert [hit.source_path for hit in ranked.hits] == [
        "sessions/task/p01.jsonl",
        "distractors/d01.jsonl",
    ]

    monkeypatch.setenv("AMB_RECALL_HOSTED_URL", "https://memory.example.test")
    monkeypatch.setenv("AMB_RECALL_HOSTED_API_KEY", "secret")
    spec = adapter.build_for_task(tmp_path / "session", "run-1", "task", "prompt")
    config = json.loads(
        spec.mcp_config and __import__("pathlib").Path(spec.mcp_config).read_text(encoding="utf-8")
    )
    server = config["mcpServers"]["recall_hosted"]
    assert server["args"] == ["-m", "adapters.recall_hosted.mcp_bridge"]
    assert spec.extra_allowed_tools == ("mcp__recall_hosted__recall_search",)
    pilot_source = (
        __import__("pathlib").Path(__file__).parents[1] / "scripts" / "pilot.py"
    ).read_text(encoding="utf-8")
    assert '"recall_hosted"' in pilot_source


def test_mcp_bridge_exposes_only_search_and_forwards_stored_evidence(monkeypatch):
    monkeypatch.setenv("RECALL_HOSTED_URL", "https://memory.example.test")
    monkeypatch.setenv("RECALL_HOSTED_API_KEY", "secret")
    monkeypatch.setenv("RECALL_HOSTED_USER_ID", "run-1")
    monkeypatch.setattr(
        mcp_bridge.HostedHttpClient,
        "request",
        lambda self, path, payload: {"data": [{"id": "one", "content": "stored evidence"}]},
    )
    listed = mcp_bridge._result({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    called = mcp_bridge._result(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "recall_search", "arguments": {"query": "failure"}},
        }
    )
    assert [tool["name"] for tool in listed["result"]["tools"]] == ["recall_search"]
    assert called["result"]["structuredContent"] == {
        "data": [{"id": "one", "content": "stored evidence"}]
    }


def test_adapter_rejects_add_response_that_does_not_echo_request_identity(monkeypatch, tmp_path):
    """`ingest` was RED: the pre-fix adapter accepted another request's success response."""
    relative = "sessions/task/p01.jsonl"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    source.write_text('{"role":"user","content":"evidence"}\n', encoding="utf-8")
    corpus = CorpusManifest(tmp_path, {relative: hashlib.sha256(source.read_bytes()).hexdigest()})
    base = tmp_path / "base.md"
    base.write_text("base", encoding="utf-8")
    adapter = RecallHostedAdapter(tmp_path / "stage", base)

    class WrongEchoClient(FakeClient):
        def request(self, path, payload=None):
            if path == "/v1/add":
                return {
                    "success": True,
                    "request_id": "wrong",
                    "user_id": payload["user_id"],
                    "session_id": payload["session_id"],
                    "raw_count": 1,
                    "compiled_count": 1,
                }
            return super().request(path, payload)

    monkeypatch.setattr(adapter, "_client", lambda **kwargs: WrongEchoClient())

    with pytest.raises(RuntimeError, match="did not echo"):
        adapter.ingest(corpus, "run-1")
