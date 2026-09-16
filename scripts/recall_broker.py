"""Dedicated capability-checked HTTP broker for the RE-call AMB arm.

The official AMB broker is shared with Graphiti on VPS2.  RE-call exposes MCP over stdio, so this
small controller-side bridge keeps the participant-facing broker boundary while maintaining one
RE-call process per signed namespace. The full-tools benchmark surface is filtered to the frozen
adapter allow-list; task instructions, capability scopes and the store's own authorization remain
the mutation boundary.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.broker import (
    BrokerApplication,
    BrokerError,
    BrokerHTTPServer,
    BrokerPolicy,
    Capability,
    SignedCapabilityAuthority,
)

TOOLS = frozenset(
    {
        "recall_apply_fact",
        "recall_calibration_publish",
        "recall_calibration_run",
        "recall_calibration_status",
        "recall_current_facts",
        "recall_current_state",
        "recall_search",
        "recall_evidence",
        "recall_forget",
        "recall_index",
        "recall_ingest",
        "recall_inventory",
        "recall_job_status",
        "recall_related",
        "recall_rewrite_plan",
        "recall_query_construction_challenge",
        "recall_reasoning_query",
        "recall_reasoning_projection",
        "recall_reasoning_proposals",
        "recall_reasoning_audit",
        "recall_stats",
        "recall_tenants",
    }
)
INITIALIZE_PARAMS = {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "amb-recall-broker", "version": "1"},
}


class RecallProcess:
    def __init__(self, namespace: str) -> None:
        root = Path(os.environ.get("AMB_RECALL_SERVING_ROOT", "/home/sentiment/recall-repos/serving"))
        python = os.environ.get(
            "AMB_RECALL_PYTHON", "/home/sentiment/recall-repos/.venv/bin/python"
        )
        # The shared VPS2 venv is created on the host and its launcher points at
        # /usr/bin/python3.12.  The broker image has the same Python ABI under
        # /usr/local/bin instead, so use the image interpreter while keeping the
        # shared venv's dependencies on PYTHONPATH.
        python_path = Path(python)
        if not python_path.is_file():
            for candidate in ("/usr/local/bin/python3.12", "/usr/local/bin/python"):
                if Path(candidate).is_file():
                    python = candidate
                    break
        site_packages = root.parent / ".venv" / "lib" / "python3.12" / "site-packages"
        if not (root / "recall_mcp" / "server.py").is_file() or not Path(python).is_file():
            raise BrokerError("RE-call serving checkout or Python runtime is unavailable")
        env = os.environ.copy()
        if site_packages.is_dir():
            existing_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = (
                str(site_packages)
                if not existing_pythonpath
                else str(site_packages) + os.pathsep + existing_pythonpath
            )
        env.update(
            {
                "RECALL_ENV": "production",
                "RECALL_TRANSPORT": "stdio",
                "RECALL_TRUST_MODE": "strict",
                "RECALL_TENANT": namespace,
                "RECALL_EMBEDDER": "voyage-context:voyage-context-4",
                "RECALL_MCP_TOOLS": ",".join(sorted(TOOLS)),
            }
        )
        self.proc = subprocess.Popen(
            [python, "-m", "recall_mcp.server"],
            cwd=str(root),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        if self.proc.stdin is None or self.proc.stdout is None:
            raise BrokerError("RE-call process did not expose stdio")
        self._next_id = 1
        self._lock = threading.RLock()
        self._request("initialize", dict(INITIALIZE_PARAMS))
        self._notify("notifications/initialized")
        self._request("tools/list", {})

    def _notify(self, method: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.proc.poll() is not None or self.proc.stdin is None or self.proc.stdout is None:
            raise BrokerError("RE-call process exited")
        request_id = self._next_id
        self._next_id += 1
        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        # The current MCP SDK treats `tools/list` with an explicit empty params object as an
        # unknown method. Omit the optional field when it carries nothing, matching the direct
        # preflight client and the protocol examples.
        if params:
            request["params"] = params
        self.proc.stdin.write(
            json.dumps(request) + "\n"
        )
        self.proc.stdin.flush()
        deadline = time.monotonic() + 180.0
        while time.monotonic() < deadline:
            if not select.select([self.proc.stdout], [], [], min(1.0, deadline - time.monotonic()))[0]:
                continue
            line = self.proc.stdout.readline()
            if not line:
                break
            try:
                reply = json.loads(line)
            except json.JSONDecodeError as error:
                raise BrokerError("RE-call emitted malformed JSON") from error
            if isinstance(reply, dict) and reply.get("id") == request_id:
                if "error" in reply:
                    error = reply.get("error")
                    message = error.get("message") if isinstance(error, dict) else error
                    raise BrokerError(f"RE-call rejected {method}: {message}")
                return reply
        raise BrokerError(f"RE-call timed out on {method}")

    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        method = str(request.get("method", ""))
        with self._lock:
            if method.startswith("notifications/"):
                self._notify(method)
                return {"jsonrpc": "2.0", "id": request.get("id"), "result": {}}
            params = request.get("params") or {}
            # AMB's broker admission probe intentionally uses an empty initialize params object.
            # The current MCP SDK validates the standard initialize fields, so fill them only for
            # that probe shape; real participant initialization already carries its own params.
            if method == "initialize" and not params:
                params = dict(INITIALIZE_PARAMS)
            reply = self._request(method, params)
            reply["id"] = request.get("id")
            if method == "tools/list":
                result = reply.get("result")
                if isinstance(result, dict) and isinstance(result.get("tools"), list):
                    result["tools"] = [
                        tool for tool in result["tools"]
                        if isinstance(tool, dict) and tool.get("name") in TOOLS
                    ]
            return reply

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()


class RecallMemoryHandler:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, RecallProcess] = {}

    def __call__(self, request: dict[str, object], grant: Capability) -> dict[str, object]:
        method = str(request.get("method", ""))
        if method == "tools/call":
            params = request.get("params")
            name = str(params.get("name", "")) if isinstance(params, dict) else ""
            if name not in TOOLS:
                raise BrokerError(f"RE-call tool {name!r} is not allowed")
        with self._lock:
            process = self._sessions.get(grant.namespace)
            if process is None:
                process = RecallProcess(grant.namespace)
                self._sessions[grant.namespace] = process
        return process.call(request)

    def close(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for process in sessions:
            process.close()


def main() -> int:
    secret = os.environ.get("AMB_BROKER_SIGNING_SECRET", "").encode("utf-8")
    if not secret:
        raise SystemExit("AMB_BROKER_SIGNING_SECRET is required")
    handler = RecallMemoryHandler()
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
        memory_handler=handler,
    )
    server = BrokerHTTPServer((os.environ.get("AMB_RECALL_BROKER_BIND", "0.0.0.0"), int(os.environ.get("AMB_RECALL_BROKER_PORT", "18083"))), application)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        handler.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
