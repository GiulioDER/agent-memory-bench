"""The preflight that decides whether a search rate means anything.

These use a fake stdio server rather than recall's, because what is being tested is the harness's
ability to tell "the server is up" from "the server is dead", and that must hold for any arm a
competitor brings.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from harness.mcp_probe import McpServerUnavailable, probe

GOOD_SERVER = '''
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"],
                          "result": {"serverInfo": {"name": "fake", "version": "1"}}}), flush=True)
    elif msg.get("method") == "tools/list":
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"],
                          "result": {"tools": [{"name": "alpha"}, {"name": "beta"}]}}), flush=True)
'''

DEAD_SERVER = '''
import sys
sys.stderr.write("ModuleNotFoundError: No module named 'mcp'\\n")
raise SystemExit(1)
'''

SILENT_SERVER = '''
import sys, time
time.sleep(30)
'''


def _config(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "server.py"
    script.write_text(body, encoding="utf-8")
    config = tmp_path / "fake.mcp.json"
    config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "fake": {"command": sys.executable, "args": [str(script)], "env": {}}
                }
            }
        ),
        encoding="utf-8",
    )
    return config


def test_a_live_server_returns_its_tools(tmp_path):
    tools = probe(_config(tmp_path, GOOD_SERVER), "fake", ["alpha", "beta"])
    assert tools == ["alpha", "beta"]


def test_a_server_that_cannot_start_is_refused_with_its_stderr(tmp_path):
    """THE case this module exists for, and it is the real one.

    `recall_mcp.server` died exactly this way on 2026-08-29 inside the pinned venv, which had
    `recall-rag[fastembed]` but not the `mcp` extra. Fourteen sessions recorded
    `memory_call_count = 0` and read as a model that chose not to search.
    """

    with pytest.raises(McpServerUnavailable) as excinfo:
        probe(_config(tmp_path, DEAD_SERVER), "fake", ["alpha"])
    message = str(excinfo.value)
    assert "No module named 'mcp'" in message, "the server's own stderr must reach the operator"
    assert "memory_call_count = 0" in message, "the message must say why a dead server is silent"


def test_a_server_that_never_answers_is_refused(tmp_path):
    with pytest.raises(McpServerUnavailable, match="no reply to initialize"):
        probe(_config(tmp_path, SILENT_SERVER), "fake", ["alpha"], timeout_s=3.0)


def test_a_live_server_missing_a_required_tool_is_refused(tmp_path):
    """Up is not the same as usable. An arm allow-listed for a tool the server does not publish
    would record zero calls and look like disuse, which is the same failure wearing a different
    hat."""

    with pytest.raises(McpServerUnavailable, match="does not offer"):
        probe(_config(tmp_path, GOOD_SERVER), "fake", ["alpha", "gamma"])
