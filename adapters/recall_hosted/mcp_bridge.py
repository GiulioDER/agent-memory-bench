"""Dependency free stdio MCP bridge for the hosted Search endpoint."""

from __future__ import annotations

import json
import os
import sys

from adapters.recall_hosted.adapter import HostedHttpClient

TOOL = "recall_search"


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
        value = client.request(
            "/v1/search",
            {
                "query": query,
                "user_id": os.environ["RECALL_HOSTED_USER_ID"],
                "top_k": top_k,
            },
        )
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
