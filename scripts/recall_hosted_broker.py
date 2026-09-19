"""Capability-checked broker for the RE-call Hosted Search MCP surface."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from adapters.recall_hosted.adapter import HostedHttpClient
from adapters.recall_hosted.mcp_bridge import _TRACE_HEADERS, TOOL
from harness.broker import (
    BrokerApplication,
    BrokerError,
    BrokerHTTPServer,
    BrokerPolicy,
    Capability,
    SignedCapabilityAuthority,
)


class RecallHostedMemoryHandler:
    def __init__(self, client: HostedHttpClient | None = None) -> None:
        self.client = client or HostedHttpClient(
            os.environ["RECALL_HOSTED_URL"],
            os.environ["RECALL_HOSTED_API_KEY"],
            timeout=float(os.environ.get("RECALL_HOSTED_TIMEOUT_SECONDS", "10")),
        )

    @staticmethod
    def _append_trace(query: str, top_k: int, grant: Capability, response: Any) -> None:
        raw_path = os.environ.get("RECALL_HOSTED_TRACE_PATH", "").strip()
        if not raw_path:
            return
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "schema_version": 1,
            "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
            "user_id_sha256": hashlib.sha256(grant.namespace.encode()).hexdigest(),
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

    def __call__(self, request: dict[str, object], grant: Capability) -> dict[str, object]:
        if grant.arm != "recall_hosted":
            raise BrokerError(f"hosted broker refuses arm {grant.arm!r}")
        request_id = request.get("id")
        method = str(request.get("method", ""))
        if method == "initialize":
            value: dict[str, object] = {
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
            params = request.get("params")
            if not isinstance(params, dict) or params.get("name") != TOOL:
                raise BrokerError("hosted broker allows only recall_search")
            arguments = params.get("arguments")
            if not isinstance(arguments, dict):
                raise BrokerError("recall_search arguments must be an object")
            query = arguments.get("query")
            if not isinstance(query, str) or not query.strip():
                raise BrokerError("recall_search query must be a nonempty string")
            top_k = int(arguments.get("top_k", 12))
            if top_k < 1 or top_k > 100:
                raise BrokerError("recall_search top_k is outside 1..100")
            response = self.client.request_with_headers(
                "/v1/search",
                {"query": query, "user_id": grant.namespace, "top_k": top_k},
            )
            self._append_trace(query, top_k, grant, response)
            value = {
                "content": [{"type": "text", "text": json.dumps(response.payload)}],
                "structuredContent": response.payload,
                "isError": False,
            }
        else:
            raise BrokerError(f"hosted broker method {method!r} is not allowed")
        return {"jsonrpc": "2.0", "id": request_id, "result": value}


def main() -> int:
    secret = os.environ.get("AMB_BROKER_SIGNING_SECRET", "").encode()
    if not secret:
        raise SystemExit("AMB_BROKER_SIGNING_SECRET is required")
    for name in ("RECALL_HOSTED_URL", "RECALL_HOSTED_API_KEY"):
        if not os.environ.get(name, "").strip():
            raise SystemExit(f"{name} is required")
    application = BrokerApplication(
        authority=SignedCapabilityAuthority(secret),
        policy=BrokerPolicy(
            service="memory",
            max_request_bytes=4 * 1024 * 1024,
            ttl_s=float(os.environ.get("AMB_BROKER_TOKEN_TTL_S", "3600")),
            network_policy_digest=os.environ.get("AMB_NETWORK_POLICY_DIGEST", ""),
        ),
        run_context={"run_id": "*", "arm": "*", "namespace": "*"},
        upstream_url="",
        memory_handler=RecallHostedMemoryHandler(),
    )
    server = BrokerHTTPServer(
        (
            os.environ.get("AMB_RECALL_HOSTED_BROKER_BIND", "0.0.0.0"),
            int(os.environ.get("AMB_RECALL_HOSTED_BROKER_PORT", "8080")),
        ),
        application,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
