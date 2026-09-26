"""Trusted HTTP to stdio bridge for the pinned Graphiti MCP server."""

from __future__ import annotations

import json
import os
import select
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .broker import BrokerError, Capability


class _GraphitiProcess:
    def __init__(self, namespace: str, *, timeout_s: float = 180.0) -> None:
        self.timeout_s = timeout_s
        root = Path(os.environ.get("GRAPHITI_MCP_DIR", "/graphiti/mcp_server")).resolve()
        main = root / "main.py"
        python = os.environ.get("GRAPHITI_PYTHON", str(root / ".venv/bin/python"))
        if not main.is_file() or not Path(python).is_file():
            raise BrokerError("Graphiti broker checkout is unavailable")
        key = os.environ.get("GRAPHITI_OPENROUTER_API_KEY", "").strip()
        if not key:
            raise BrokerError("Graphiti broker credential is unavailable")
        database = os.environ.get("GRAPHITI_DATABASE_PROVIDER", "falkordb").strip().lower()
        if database != "falkordb":
            raise BrokerError("Graphiti broker only permits the configured FalkorDB backend")
        api_url = os.environ.get("GRAPHITI_OPENAI_API_URL", "https://openrouter.ai/api/v1")
        proxy = os.environ.get("AMB_EGRESS_PROXY_URL", "").strip()
        if not proxy:
            raise BrokerError("Graphiti broker egress proxy is unavailable")
        env = os.environ.copy()
        env.update(
            {
                "OPENAI_API_KEY": key,
                "OPENAI_API_URL": api_url,
                "LLM__PROVIDERS__OPENAI__API_KEY": key,
                "LLM__PROVIDERS__OPENAI__API_URL": api_url,
                "EMBEDDER__PROVIDERS__OPENAI__API_KEY": os.environ.get("GRAPHITI_EMBEDDER_API_KEY", key),
                "EMBEDDER__PROVIDERS__OPENAI__API_URL": os.environ.get(
                    "GRAPHITI_EMBEDDER_API_URL", api_url
                ),
                "GRAPHITI_GROUP_ID": namespace,
                "GRAPHITI_TELEMETRY_ENABLED": "false",
                "FALKORDB_URI": os.environ.get("GRAPHITI_FALKORDB_URI", "redis://amb-falkordb:6379"),
                "FALKORDB_DATABASE": os.environ.get("GRAPHITI_FALKORDB_DATABASE", "amb_graphiti"),
                "MODEL_NAME": os.environ.get("GRAPHITI_MODEL_NAME", "deepseek/deepseek-v4-flash"),
                "EMBEDDER_MODEL": os.environ.get("GRAPHITI_EMBEDDER_MODEL", "text-embedding-3-small"),
                "LLM_STRUCTURED_OUTPUT_MODE": os.environ.get(
                    "GRAPHITI_LLM_STRUCTURED_OUTPUT_MODE", "json_schema"
                ),
                "SEMAPHORE_LIMIT": os.environ.get("GRAPHITI_SEMAPHORE_LIMIT", "1"),
                "HTTP_PROXY": proxy,
                "HTTPS_PROXY": proxy,
                "NO_PROXY": "amb-falkordb,localhost,127.0.0.1",
            }
        )
        self.proc = subprocess.Popen(
            [
                python,
                str(main),
                "--transport", "stdio",
                "--llm-provider", os.environ.get("GRAPHITI_LLM_PROVIDER", "openai"),
                "--model", env["MODEL_NAME"],
                "--embedder-provider", os.environ.get("GRAPHITI_EMBEDDER_PROVIDER", "openai"),
                "--embedder-model", env["EMBEDDER_MODEL"],
                "--database-provider", database,
                "--group-id", namespace,
            ],
            cwd=str(root), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            # Graphiti is a verbose third-party process. An undrained PIPE here can fill and
            # deadlock the stdio bridge after several large episodes, leaving the controller
            # waiting forever on an otherwise healthy-looking child. Diagnostics are deliberately
            # discarded because they may contain provider or transcript data.
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        if self.proc.stdin is None or self.proc.stdout is None:
            raise BrokerError("Graphiti broker process did not expose stdio")
        self._next_id = 1
        self._lock = threading.RLock()
        self._request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}})
        self._notify("notifications/initialized")
        self._request("tools/list", {})

    def _notify(self, method: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.proc.poll() is not None or self.proc.stdin is None or self.proc.stdout is None:
            raise BrokerError("Graphiti broker process exited")
        request_id = self._next_id
        self._next_id += 1
        self.proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n"
        )
        self.proc.stdin.flush()
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if not select.select([self.proc.stdout], [], [], remaining)[0]:
                break
            line = self.proc.stdout.readline()
            if not line:
                break
            try:
                reply = json.loads(line)
            except json.JSONDecodeError as error:
                raise BrokerError("Graphiti broker emitted malformed JSON") from error
            if isinstance(reply, dict) and reply.get("id") == request_id:
                return reply
        raise BrokerError(f"Graphiti broker timed out on {method}")

    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        method = str(request.get("method", ""))
        request_id = request.get("id")
        with self._lock:
            if method == "initialize":
                return {"jsonrpc": "2.0", "id": request_id, "result": {
                    "protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                    "serverInfo": {"name": "graphiti-broker", "version": "1"},
                }}
            if method.startswith("notifications/"):
                self._notify(method)
                return {"jsonrpc": "2.0", "id": request_id, "result": {}}
            reply = self._request(method, request.get("params") or {})
            reply["id"] = request_id
            return reply

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()


class GraphitiMemoryHandler:
    """Scope Graphiti MCP processes by the namespace in the signed capability."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, _GraphitiProcess] = {}
        self._allowed = {
            item.strip() for item in os.environ.get(
                "AMB_GRAPHITI_ALLOWED_TOOLS",
                "search_memory_facts,search_nodes,get_episodes,get_episode_entities,get_entity_edge,get_status",
            ).split(",") if item.strip()
        }

    def __call__(self, request: dict[str, object], grant: Capability) -> dict[str, object]:
        if request.get("method") == "tools/call":
            params = request.get("params") or {}
            name = str(params.get("name", "")) if isinstance(params, dict) else ""
            controller_write = (
                name == "add_memory"
                and grant.arm == "__controller__"
            )
            if name not in self._allowed and not controller_write:
                raise BrokerError(f"Graphiti tool {name!r} is not allowed")
        with self._lock:
            session = self._sessions.get(grant.namespace)
            if session is not None and session.proc.poll() is not None:
                # An upstream Graphiti child can be killed outside this handler, for example by
                # a cgroup cleanup after an interrupted run. Do not turn that stale cache entry
                # into a broker-level 403 on the next request; evict it and create a fresh child.
                self._sessions.pop(grant.namespace, None)
                session.close()
                session = None
            if session is None:
                session = _GraphitiProcess(grant.namespace)
                self._sessions[grant.namespace] = session
        try:
            response = session.call(request)
        except BrokerError:
            # Do not retain a wedged or exited child in the namespace cache. A subsequent
            # controller retry must get a fresh process rather than inheriting the dead session.
            with self._lock:
                if self._sessions.get(grant.namespace) is session:
                    self._sessions.pop(grant.namespace, None)
            session.close()
            raise
        if request.get("method") == "tools/list":
            result = response.get("result")
            if isinstance(result, dict) and isinstance(result.get("tools"), list):
                result["tools"] = [
                    tool for tool in result["tools"]
                    if isinstance(tool, dict) and tool.get("name") in self._allowed
                ]
        return response

    def close(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()
