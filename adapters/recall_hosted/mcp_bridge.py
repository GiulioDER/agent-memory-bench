"""Dependency free stdio MCP bridge for the hosted Search endpoint."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from adapters.recall_hosted.adapter import HostedHttpClient

TOOL = "recall_search"

_TRACE_HEADERS = (
    "x-recall-reranker-attempted",
    "x-recall-reranker-completed",
    "x-recall-reranker-provider",
    "x-recall-reranker-model",
    "x-recall-reranker-input-count",
    "x-recall-reranker-output-count",
    "x-recall-reranker-permutation-valid",
    "x-recall-reranker-top10-order-changed",
    "x-recall-reranker-top10-membership-changed",
    "x-recall-reranker-top100-order-changed",
    "x-recall-reranker-top100-membership-changed",
    "x-recall-reranker-ms",
    "x-recall-search-ms",
    "x-recall-reranker-candidate-chars",
    "x-recall-reranker-estimated-cost-usd",
    "x-recall-reranker-fallback",
    "x-recall-served-commit",
    "x-recall-generation",
    "x-recall-corpus-sha256",
    "x-recall-variant",
    "x-recall-code-aware-attempted",
    "x-recall-code-aware-fallback",
    "x-recall-code-profile",
    "x-recall-code-rrf-weight",
    "x-recall-code-query-tokens",
    "x-recall-code-match-candidates",
    "x-recall-code-top10-order-changed",
    "x-recall-code-top10-membership-changed",
    "x-recall-code-top100-order-changed",
    "x-recall-code-top100-membership-changed",
    "x-recall-neighbour-seed-limit",
    "x-recall-neighbour-seeds",
    "x-recall-neighbour-activated-seeds",
    "x-recall-neighbour-ineligible-seeds",
    "x-recall-neighbour-restored",
    "x-recall-neighbour-invalid",
    "x-recall-code-duplicate-outputs",
)


def _append_trace(query: str, top_k: int, response) -> None:
    raw_path = os.environ.get("RECALL_HOSTED_TRACE_PATH", "").strip()
    if not raw_path:
        return
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema_version": 1,
        "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
        "user_id_sha256": hashlib.sha256(os.environ["RECALL_HOSTED_USER_ID"].encode()).hexdigest(),
        "top_k": top_k,
        "items_returned": len(response.payload.get("data", [])),
        "wall_time_ms": response.wall_time_ms,
        "headers": {name: response.headers.get(name) for name in _TRACE_HEADERS},
    }
    encoded = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, encoded)
    finally:
        os.close(descriptor)


def _result(request: dict) -> dict | None:
    request_id = request.get("id")
    method = request.get("method")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        value = {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "recall-hosted", "version": "1.0.0"},
        }
    elif method == "tools/list":
        value = {
            "tools": [
                {
                    "name": TOOL,
                    "description": "Search stored evidence from prior coding sessions.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "top_k": {"type": "integer", "minimum": 1, "maximum": 100},
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                }
            ]
        }
    elif method == "tools/call":
        params = request.get("params", {})
        if params.get("name") != TOOL:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": "unknown tool"},
            }
        arguments = params.get("arguments", {})
        query = arguments.get("query", "")
        top_k = int(arguments.get("top_k", os.environ.get("RECALL_HOSTED_TOP_K", "12")))
        client = HostedHttpClient(
            os.environ["RECALL_HOSTED_URL"],
            os.environ["RECALL_HOSTED_API_KEY"],
            timeout=10,
        )
        response = client.request_with_headers(
            "/v1/search",
            {
                "query": query,
                "user_id": os.environ["RECALL_HOSTED_USER_ID"],
                "top_k": top_k,
            },
        )
        _append_trace(query, top_k, response)
        value = response.payload
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(value)}],
                "structuredContent": value,
                "isError": False,
            },
        }
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "method not found"},
        }
    return {"jsonrpc": "2.0", "id": request_id, "result": value}


def main() -> None:
    for line in sys.stdin:
        try:
            response = _result(json.loads(line))
        except Exception as exc:  # noqa: BLE001  # protocol response is safer than a dead bridge
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": type(exc).__name__},
            }
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
