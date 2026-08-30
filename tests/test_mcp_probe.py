"""The preflight that decides whether a search rate means anything.

These use a fake stdio server rather than recall's, because what is being tested is the harness's
ability to tell "the server is up" from "the server is dead", and that must hold for any arm a
competitor brings.
"""

from __future__ import annotations

import json
import sys
import time
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

#: Alive, holding stdout open, never writing. The case `SILENT_SERVER` cannot reach, because it
#: exits and its EOF is what used to end the wait.
WEDGED_SERVER = """
import time
time.sleep(120)
"""

#: Answers `initialize`, then goes quiet. The `tools/list` read had no deadline at all.
WEDGES_AFTER_INITIALIZE = """
import json, sys, time
sys.stdin.readline()
sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}) + chr(10))
sys.stdout.flush()
time.sleep(120)
"""

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
    """⚠️ The elapsed-time assertion is the whole test; the message was never the problem.

    This passed for months while `timeout_s` bounded nothing, because `SILENT_SERVER` sleeps 30
    seconds and then EXITS, closing the pipe. `readline()` returned on that EOF, the probe then
    noticed its deadline had passed, and raised the expected message. Measured 2026-08-30: green
    in 30.07s against a 3s budget. What ended the wait was the child dying, not the timeout.

    A test that asserts only the message cannot tell those two apart, and the preflight this
    guards is the thing standing between a wedged MCP server and the official run.
    """

    started = time.monotonic()
    with pytest.raises(McpServerUnavailable, match="no reply to initialize"):
        probe(_config(tmp_path, SILENT_SERVER), "fake", ["alpha"], timeout_s=3.0)
    elapsed = time.monotonic() - started
    assert elapsed < 15.0, (
        f"refused after {elapsed:.1f}s against a 3s timeout: the wait ended because the fake "
        f"server exited at 30s, not because the deadline fired"
    )


def test_a_server_that_stays_alive_and_silent_is_refused_within_its_timeout(tmp_path):
    """The case the exiting fake could never reach: a server that holds stdout open forever.

    RED before the fix, and not as a failure -- `probe()` never returned at all, because
    `readline()` blocks until a line arrives or the pipe closes and this server does neither.
    A 120s sleep against a 2s budget, so a pass cannot be the child exiting.
    """

    started = time.monotonic()
    with pytest.raises(McpServerUnavailable, match="no reply to initialize"):
        probe(_config(tmp_path, WEDGED_SERVER), "fake", ["alpha"], timeout_s=2.0)
    elapsed = time.monotonic() - started
    assert elapsed < 20.0, f"took {elapsed:.1f}s against a 2s timeout"


def test_a_server_that_wedges_after_initialize_is_refused(tmp_path):
    """Answering `initialize` and then going quiet is the shape observed on VPS2.

    The frozen config's own `reranker` note records a recall server idle at 0.3% CPU with every
    call timing out at 90s. The `tools/list` read had no deadline at all, so this hung forever.
    """

    started = time.monotonic()
    with pytest.raises(McpServerUnavailable, match="no reply to tools/list"):
        probe(_config(tmp_path, WEDGES_AFTER_INITIALIZE), "fake", ["alpha"], timeout_s=2.0)
    elapsed = time.monotonic() - started
    assert elapsed < 20.0, f"took {elapsed:.1f}s against a 2s timeout"


def test_a_live_server_missing_a_required_tool_is_refused(tmp_path):
    """Up is not the same as usable. An arm allow-listed for a tool the server does not publish
    would record zero calls and look like disuse, which is the same failure wearing a different
    hat."""

    with pytest.raises(McpServerUnavailable, match="does not offer"):
        probe(_config(tmp_path, GOOD_SERVER), "fake", ["alpha", "gamma"])
