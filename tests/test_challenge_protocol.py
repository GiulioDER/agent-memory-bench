"""Tests for the fixed evaluator to memory sidecar protocol."""

from __future__ import annotations

import json

import pytest

from harness.challenge_protocol import (
    ADAPTER_API,
    ChallengeProtocolError,
    make_request,
    parse_response,
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
