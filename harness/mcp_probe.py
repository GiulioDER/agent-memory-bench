"""Prove an arm's MCP server actually starts, before spending a run on it.

## Why this exists

A stdio MCP server that fails to start is INVISIBLE in a session record. The model simply has no
memory tools, so it answers from the sandbox and the record shows ``memory_call_count = 0``, which
is exactly what an agent that chose not to search records. `error` is null, the turn counts are
ordinary, and nothing anywhere says the arm was crippled.

That happened twice on 2026-08-29, both times on `abstention-002`, and cost 22 sessions:

1. the server started on a PATH ``python`` holding a development worktree, which refused a corpus
   written by the pinned version with ``SchemaTooNew: unknown migration(s) ['0015']``;
2. after that was fixed, the pinned venv had ``recall-rag[fastembed]`` but not the ``mcp`` extra,
   so ``recall_mcp.server`` died on ``ModuleNotFoundError: No module named 'mcp'``.

Both were found by noticing a search rate of zero and then driving the server by hand. Neither
would have been found by any test in the suite, because both are properties of the environment the
server is launched into rather than of any code under test.

## What it checks

The minimum that distinguishes "the server is there" from "the model didn't search": the JSON-RPC
handshake and the tool list. If the server answers `initialize` and offers the tools the arm is
allowed to call, a later ``memory_call_count = 0`` is a fact about the model. If it does not, the
number means nothing and the run should not start.

This is deliberately NOT a retrieval check. Whether the corpus answers well is the experiment;
whether the server is alive is a precondition.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from collections.abc import Sequence
from pathlib import Path


class McpServerUnavailable(RuntimeError):
    """The configured MCP server did not come up, so an arm's search rate would be meaningless."""



def _bounded_reader(stream):
    """A daemon thread draining `stream` into a queue, so a read can be given a deadline.

    `proc.stdout.readline()` cannot be interrupted, so the only way to bound it is to do it on
    another thread and wait on the queue instead. The thread is a daemon and the queue is
    unbounded, so nothing here can keep the interpreter alive or block on a full queue if the
    caller gives up.

    `select` is not an option: it does not accept a pipe handle on Windows, and this repository is
    developed there and run on Linux.
    """

    lines: queue.Queue[str | None] = queue.Queue()

    def pump() -> None:
        try:
            for line in iter(stream.readline, ""):
                lines.put(line)
        except (ValueError, OSError):  # pragma: no cover - the pipe closed under us
            pass
        finally:
            lines.put(None)  # EOF sentinel, so a reader can tell "closed" from "still quiet"

    thread = threading.Thread(target=pump, daemon=True, name="mcp-probe-reader")
    thread.start()
    return lines


def _read_line(lines, deadline: float, proc) -> str:
    """One line, or "" if the deadline passes or the stream ends. Never blocks past `deadline`."""

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return ""
        try:
            line = lines.get(timeout=min(remaining, 0.25))
        except queue.Empty:
            # Poll for a died-without-answering child, which the queue cannot report until the
            # pipe closes, and which is a different diagnosis from a silent one.
            if proc.poll() is not None:
                return ""
            continue
        if line is None:
            return ""
        if line.strip():
            return line


def probe(
    mcp_config_path: str | Path,
    server_name: str,
    required_tools: Sequence[str],
    *,
    timeout_s: float = 120.0,
) -> list[str]:
    """Start the server from its generated config and return the tool names it offers.

    Raises :class:`McpServerUnavailable` if it does not answer, or answers without a required tool.
    ``required_tools`` are bare names as the server publishes them, without the harness's
    ``mcp__<server>__`` prefix.
    """

    config_path = Path(mcp_config_path)
    server = json.loads(config_path.read_text(encoding="utf-8"))["mcpServers"][server_name]
    argv = [str(server["command"]), *[str(a) for a in server["args"]]]
    env = {str(k): str(v) for k, v in server.get("env", {}).items()}

    proc = subprocess.Popen(
        argv,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        # Explicit, because Popen defaults to the locale codec and that is cp1252 on
        # Windows: a single non-ASCII byte from the server raises UnicodeDecodeError
        # inside readline and looks like a dead server.
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def send(payload: dict) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

    def fail(reason: str) -> None:
        proc.kill()
        _out, err = proc.communicate(timeout=15)
        raise McpServerUnavailable(
            f"{server_name}: {reason}\n"
            f"  command: {' '.join(argv)}\n"
            f"  stderr : {(err or '').strip()[-1200:]}\n"
            f"A dead server records as memory_call_count = 0, which is indistinguishable from a "
            f"model that chose not to search, so the run is refused rather than started."
        )

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "harness-preflight", "version": "1"},
                },
            }
        )

        assert proc.stdout is not None
        lines = _bounded_reader(proc.stdout)
        deadline = time.monotonic() + timeout_s
        line = _read_line(lines, deadline, proc)
        if not line.strip():
            if proc.poll() is not None:
                fail(f"process exited {proc.returncode} before answering initialize")
            fail(f"no reply to initialize within {timeout_s:.0f}s")

        try:
            json.loads(line)
        except json.JSONDecodeError:
            fail(f"non-JSON on stdout: {line[:400]!r}")

        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        # The same bound applies here. A server that answers `initialize` and then wedges is the
        # shape the config's own `reranker` note records on VPS2: idle at 0.3% CPU, every call
        # timing out. Without a deadline this read hangs the preflight forever.
        reply = _read_line(lines, time.monotonic() + timeout_s, proc)
        if not reply.strip():
            fail(f"no reply to tools/list within {timeout_s:.0f}s")
        try:
            tools = [t["name"] for t in json.loads(reply)["result"]["tools"]]
        except (json.JSONDecodeError, KeyError, TypeError):
            fail(f"could not read tools/list reply: {reply[:400]!r}")

        missing = [t for t in required_tools if t not in tools]
        if missing:
            fail(f"server is up but does not offer {missing}; it offers {sorted(tools)}")
        return tools
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.communicate(timeout=15)
            except subprocess.TimeoutExpired:  # pragma: no cover - only on a wedged server
                proc.kill()
                proc.communicate()
