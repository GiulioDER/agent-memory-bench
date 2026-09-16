"""The capability broker must preserve the frozen full RE-call surface."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from harness.broker import BrokerError
from scripts import recall_broker

ROOT = Path(__file__).resolve().parents[1]


class _Process:
    def __init__(self, reply: dict) -> None:
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(json.dumps(reply) + "\n")

    @staticmethod
    def poll() -> None:
        return None


def _process(reply: dict) -> recall_broker.RecallProcess:
    process = recall_broker.RecallProcess.__new__(recall_broker.RecallProcess)
    process.proc = _Process(reply)
    process._next_id = 1
    return process


def test_broker_allowlist_matches_the_frozen_fulltools_adapter() -> None:
    config = json.loads(
        (ROOT / "adapters" / "recall_graph_fulltools" / "config.frozen.json").read_text(
            encoding="utf-8"
        )
    )
    assert recall_broker.TOOLS == frozenset(config["allowed_tools"])
    assert len(recall_broker.TOOLS) == 22


def test_initialize_contract_identifies_the_broker_client() -> None:
    assert recall_broker.INITIALIZE_PARAMS == {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "amb-recall-broker", "version": "1"},
    }


def test_empty_params_are_omitted_for_current_mcp_sdk(monkeypatch) -> None:
    process = _process({"jsonrpc": "2.0", "id": 1, "result": {"tools": []}})
    monkeypatch.setattr(recall_broker.select, "select", lambda *_args, **_kwargs: ([1], [], []))
    reply = process._request("tools/list", {})
    sent = json.loads(process.proc.stdin.getvalue())
    assert "params" not in sent
    assert reply["result"] == {"tools": []}


def test_upstream_jsonrpc_error_is_not_misreported_as_an_empty_surface(monkeypatch) -> None:
    process = _process(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32601, "message": "Method not found"},
        }
    )
    monkeypatch.setattr(recall_broker.select, "select", lambda *_args, **_kwargs: ([1], [], []))
    with pytest.raises(BrokerError, match="rejected tools/list: Method not found"):
        process._request("tools/list", {})
