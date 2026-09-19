from __future__ import annotations

import json
import time

import pytest

from adapters.recall_hosted.adapter import HostedHttpResponse
from harness.broker import BrokerError, Capability
from scripts import pilot
from scripts.recall_hosted_broker import RecallHostedMemoryHandler


class FakeHostedClient:
    def __init__(self):
        self.calls = []

    def request_with_headers(self, path, payload):
        self.calls.append((path, payload))
        return HostedHttpResponse(
            {"data": [{"text": "evidence"}]},
            {
                "x-recall-variant": "M1_code_neighbors",
                "x-recall-code-aware-fallback": "0",
            },
            12.5,
        )


def _grant(arm: str = "recall_hosted") -> Capability:
    return Capability(
        run_id="run",
        arm=arm,
        namespace="shared-corpus",
        service="memory",
        allowed_methods=("initialize", "tools/list", "tools/call"),
        expires_at=time.time() + 60,
    )


def test_hosted_broker_routes_capability_namespace_and_records_outer_latency(
    tmp_path, monkeypatch
):
    trace = tmp_path / "trace.jsonl"
    monkeypatch.setenv("RECALL_HOSTED_TRACE_PATH", str(trace))
    client = FakeHostedClient()
    handler = RecallHostedMemoryHandler(client)

    reply = handler(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "recall_search",
                "arguments": {"query": "save(path)", "top_k": 8},
            },
        },
        _grant(),
    )

    assert client.calls == [
        (
            "/v1/search",
            {"query": "save(path)", "user_id": "shared-corpus", "top_k": 8},
        )
    ]
    assert reply["result"]["structuredContent"]["data"]
    row = json.loads(trace.read_text(encoding="utf-8"))
    assert row["wall_time_ms"] == 12.5
    assert row["headers"]["x-recall-variant"] == "M1_code_neighbors"


def test_hosted_broker_refuses_another_memory_arm():
    with pytest.raises(BrokerError, match="refuses arm"):
        RecallHostedMemoryHandler(FakeHostedClient())(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            _grant("recall"),
        )


def test_hosted_arm_uses_real_search_preflight_without_a_recall_dsn():
    assert "recall_hosted" in pilot.RECALL_ARMS
    assert pilot.recall_preflight_request("recall_hosted", "task") == (
        "recall_search",
        {"query": "task", "top_k": 1},
    )
