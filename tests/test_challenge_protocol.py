"""Tests for the fixed evaluator to memory sidecar protocol."""

from __future__ import annotations

import json
import math
import socket

import pytest

from harness.challenge_protocol import (
    ADAPTER_API,
    ChallengeProtocolError,
    make_request,
    parse_response,
    request_unix_socket,
)


def test_request_is_versioned_and_newline_delimited():
    payload = json.loads(
        make_request("req-1", "search", {"task_id": "task-a", "query": "find it"})
    )
    assert payload == {
        "api": ADAPTER_API,
        "id": "req-1",
        "method": "search",
        "params": {"task_id": "task-a", "query": "find it"},
    }


@pytest.mark.parametrize(
    "method",
    ["ingest", "shutdown", "unknown"],
)
def test_request_rejects_methods_outside_fixed_protocol(method: str):
    with pytest.raises(ChallengeProtocolError, match="unsupported adapter method"):
        make_request("req-1", method)


def test_response_requires_matching_version_id_and_shape():
    response = parse_response(
        json.dumps(
            {
                "api": ADAPTER_API,
                "id": "req-1",
                "ok": True,
                "result": {"hits": []},
            }
        ),
        "req-1",
    )
    assert response["result"] == {"hits": []}


def test_search_response_has_a_fixed_result_shape():
    response = parse_response(
        json.dumps(
            {
                "api": ADAPTER_API,
                "id": "req-1",
                "ok": True,
                "result": {
                    "hits": [
                        {"source_id": "session-1", "text": "memory", "score": 0.9, "rank": 1}
                    ],
                    "abstained": False,
                    "usage": {"input_tokens": 3, "output_tokens": 0},
                },
            }
        ),
        "req-1",
        method="search",
    )
    assert response["result"]["hits"][0]["rank"] == 1


def test_search_response_rejects_uncontracted_fields():
    with pytest.raises(ChallengeProtocolError, match="unexpected field set"):
        parse_response(
            json.dumps(
                {
                    "api": ADAPTER_API,
                    "id": "req-1",
                    "ok": True,
                    "result": {
                        "hits": [],
                        "abstained": False,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                        "answer": "hidden channel",
                    },
                }
            ),
            "req-1",
            method="search",
        )


def test_socket_request_rejects_a_regular_file_at_the_adapter_path(tmp_path):
    if not hasattr(socket, "AF_UNIX"):
        pytest.skip("Unix sockets are unavailable on this host")
    socket_path = tmp_path / "adapter.sock"
    socket_path.write_text("not a socket", encoding="utf-8")
    with pytest.raises(ChallengeProtocolError, match="not a Unix socket"):
        request_unix_socket(str(socket_path), "req-1", "health")


@pytest.mark.parametrize("timeout_seconds", [True, 0, -1, math.nan, math.inf, "1"])
def test_socket_request_rejects_invalid_timeouts(timeout_seconds):
    with pytest.raises(ChallengeProtocolError, match="finite and positive"):
        request_unix_socket("unused.sock", "req-1", "health", timeout_seconds=timeout_seconds)


@pytest.mark.parametrize(
    "params",
    [
        {"query": "find it"},
        {"task_id": "task-a", "query": ""},
        {"task_id": "task-a", "query": "find it", "limit": 0},
        {"task_id": "task-a", "query": "find it", "limit": 101},
    ],
)
def test_search_request_rejects_missing_or_unbounded_parameters(params: dict):
    with pytest.raises(ChallengeProtocolError):
        make_request("req-1", "search", params)


@pytest.mark.parametrize(
    "response",
    [
        {"api": "wrong", "id": "req-1", "ok": True, "result": {}},
        {"api": ADAPTER_API, "id": "other", "ok": True, "result": {}},
        {"api": ADAPTER_API, "id": "req-1", "ok": True},
        {"api": ADAPTER_API, "id": "req-1", "ok": False},
    ],
)
def test_response_rejects_malformed_envelopes(response: dict):
    with pytest.raises(ChallengeProtocolError):
        parse_response(json.dumps(response), "req-1")
