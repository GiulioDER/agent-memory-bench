"""Run a bounded live MCP smoke test for the graph plus Voyage reranker path."""

from __future__ import annotations

import json
import subprocess
from typing import Any


HOST = "sentiment@100.91.148.25"
TENANT = "amb-smoke-graph-rerank"
REMOTE = (
    "cd /home/sentiment/recall-repos/serving && "
    "set -a && . ../.env && set +a && "
    "RECALL_ENV=production RECALL_TRUST_MODE=development "
    f"RECALL_TENANT={TENANT} "
    "RECALL_EMBEDDER=voyage-context:voyage-context-4 "
    "RECALL_INDEX_ROOT=/home/sentiment/recall-repos "
    "RECALL_RERANK=1 RECALL_RERANK_MODEL=voyage:rerank-2.5 "
    "../.venv/bin/python -m recall_mcp.server"
)


def _call(proc: subprocess.Popen[str], counter: list[int], name: str, args: dict[str, Any]) -> dict:
    assert proc.stdin is not None
    assert proc.stdout is not None
    request_id = counter[0]
    counter[0] += 1
    proc.stdin.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": args},
            }
        )
        + "\n"
    )
    proc.stdin.flush()
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("live MCP server closed before answering the smoke call")
        message = json.loads(line)
        if message.get("id") == request_id:
            return message


def _payload(message: dict) -> dict:
    """Decode the first MCP text content block returned by a tool."""
    result = message.get("result", {})
    for block in result.get("content", []):
        if block.get("type") == "text":
            return json.loads(block["text"])
    raise RuntimeError(f"MCP response has no JSON text payload: {message!r}")


def main() -> int:
    proc = subprocess.Popen(
        ["ssh", "-T", "-o", "BatchMode=yes", HOST, REMOTE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    counter = [1]
    try:
        assert proc.stdin is not None
        proc.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": counter[0],
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "amb-smoke", "version": "1"},
                    },
                }
            )
            + "\n"
        )
        proc.stdin.flush()
        counter[0] += 1
        assert proc.stdout is not None
        while True:
            if not proc.stdout.readline():
                raise RuntimeError("live MCP server closed during initialize")
            break
        proc.stdin.write(
            json.dumps(
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
            )
            + "\n"
        )
        proc.stdin.flush()
        initial_stats = _call(proc, counter, "recall_stats", {})
        graph = _call(
                proc,
                counter,
                "recall_reasoning_query",
                {
                    "query": "smoke policy supports",
                    "graph_expansion": "one_hop",
                    "expand_retrieval": False,
                    "k": 1,
                    "max_graph_nodes": 10,
                    "max_evidence_tokens": 100,
                    "mode": "evidence_assembly",
                },
            )
        search = _call(
                proc,
                counter,
                "recall_search",
                {"query": "smoke policy smoke service", "k": 5, "explain": True},
            )
        final_stats = _call(proc, counter, "recall_stats", {})

        graph_payload = _payload(graph)
        graph_diagnostics = graph_payload.get("diagnostics", {})
        search_payload = _payload(search)
        summary = {
            "graph_metadata_fixture": "2 documents, 2 persisted relations",
            "graph_mode": graph_diagnostics.get("graph_expansion_mode"),
            "graph_readiness": graph_diagnostics.get("graph_readiness"),
            "graph_entities_inspected": graph_diagnostics.get("graph_entities_inspected"),
            "graph_relations_inspected": graph_diagnostics.get("graph_relations_inspected"),
            "graph_relation_seed_activations": graph_diagnostics.get(
                "graph_relation_seed_activations"
            ),
            "graph_candidates_discovered": graph_diagnostics.get("graph_candidates_discovered"),
            "graph_candidates_accepted": graph_diagnostics.get("graph_relation_candidates_accepted"),
            "graph_gate_reason": graph_diagnostics.get("graph_gate_reason"),
            "graph_rerank_ms": graph_diagnostics.get("retrieval_stage_ms", {}).get("reranking"),
            "embedding_profile": search_payload.get("embedding_profile"),
            "retrieval_profile": search_payload.get("retrieval_profile"),
            "reranking_ran": search_payload.get("reranking_ran"),
            "rerank_ms": search_payload.get("rerank_ms"),
            "generation_id": search_payload.get("generation_id"),
            "calibration_status": search_payload.get("calibration_status"),
            "initial_stats": _payload(initial_stats),
            "final_stats": _payload(final_stats),
        }
        print(json.dumps(summary, indent=2))
        assert summary["graph_mode"] == "one_hop"
        assert summary["graph_readiness"] == "ready"
        assert summary["graph_relations_inspected"] > 0
        assert summary["graph_relation_seed_activations"]
        assert summary["graph_rerank_ms"] > 0
        assert summary["embedding_profile"] == "voyage-context-4-v1"
        assert summary["reranking_ran"] is True
        assert summary["rerank_ms"] > 0
        assert summary["calibration_status"] == "certified"
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
