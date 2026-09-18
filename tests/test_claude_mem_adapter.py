"""Claude-Mem adapter tests that do not start a vendor worker or call a model."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from adapters.claude_mem.adapter import ClaudeMemAdapter
from harness import instructions
from harness.instructions import APPENDIX_MAX_BYTES

REPO = Path(__file__).resolve().parents[1]
CONFIG = json.loads(
    (REPO / "adapters" / "claude_mem" / "config.frozen.json").read_text(encoding="utf-8")
)


def _fake_plugin(root: Path) -> Path:
    plugin = root / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / "hooks").mkdir()
    (plugin / "scripts").mkdir()
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "claude-mem", "version": CONFIG["plugin_version"]}),
        encoding="utf-8",
    )
    (plugin / ".mcp.json").write_text('{"mcpServers": {}}\n', encoding="utf-8")
    (plugin / "hooks" / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "Setup": [{"hooks": [{"type": "command", "command": "setup"}]}],
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "start"}]},
                        {"hooks": [{"type": "command", "command": "context"}]},
                    ],
                    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "init"}]}],
                    "PostToolUse": [{"hooks": [{"type": "command", "command": "observe"}]}],
                    "PreToolUse": [
                        {"hooks": [{"type": "command", "command": "file", "async": True}]}
                    ],
                    "Stop": [{"hooks": [{"type": "command", "command": "summarize"}]}],
                }
            }
        ),
        encoding="utf-8",
    )
    for name in ("bun-runner.js", "worker-service.cjs", "mcp-server.cjs", "version-check.js"):
        (plugin / "scripts" / name).write_text("// test fixture\n", encoding="utf-8")
    return root


def test_the_arm_is_registered_in_runner_and_abstention_rosters():
    from scripts import abstention, pilot

    assert "claude_mem" in pilot.ARMS
    assert "claude_mem" in pilot.MEMORY_ARMS
    assert "claude_mem" in pilot.SELF_INGESTING_ARMS
    assert "claude_mem" in abstention.MEMORY_ARMS


def test_instruction_uses_the_shared_protocol_and_capped_appendix():
    instruction = ClaudeMemAdapter.shared_instruction()
    instructions.assert_shared_protocol({"claude_mem": instruction})
    assert "mcp__mcp-search__search" in instruction
    assert "MANDATORY FIRST ACTION" in instruction
    assert "before using Read, Write, Edit, Glob, Grep, or Bash" in instruction
    appendix = (REPO / "adapters" / "claude_mem" / "instruction_appendix.md").read_bytes()
    assert 0 < len(appendix) <= APPENDIX_MAX_BYTES


def test_build_uses_the_pinned_official_server_and_hooks(tmp_path, monkeypatch):
    plugin_root = _fake_plugin(tmp_path / "vendor")
    base_prompt = tmp_path / "base.md"
    base_prompt.write_text("# Fixture\n", encoding="utf-8")
    monkeypatch.setenv(CONFIG["plugin_dir_env"], str(plugin_root))
    monkeypatch.setenv(CONFIG["observer_api_key_env"], "test-key")
    monkeypatch.setenv("CLAUDE_MEM_ENFORCE_FIRST_SEARCH", "1")

    adapter = ClaudeMemAdapter(tmp_path / "staging", base_prompt)
    spec = adapter.build_for_task(tmp_path / "session", "namespace", "task", "do it")

    mcp = json.loads(Path(spec.mcp_config).read_text(encoding="utf-8"))
    server = mcp["mcpServers"][CONFIG["server_name"]]
    assert server["args"][-1].endswith("scripts\\mcp-server.cjs") or server["args"][-1].endswith(
        "scripts/mcp-server.cjs"
    )
    assert spec.memory_tool_prefix == CONFIG["tool_prefix"]
    assert spec.extra_allowed_tools == tuple(
        f"{CONFIG['tool_prefix']}{tool}" for tool in CONFIG["tools"]
    )
    assert spec.extra_args == ("--plugin-dir", str(Path(spec.config_dir) / "plugin"))
    settings = json.loads((Path(spec.config_dir) / "settings.json").read_text(encoding="utf-8"))
    assert set(CONFIG["required_hooks"]).issubset(settings["hooks"])
    assert "SessionStartWorker" in json.dumps(settings)
    assert all("async" not in hook for group in settings["hooks"]["PreToolUse"] for hook in group["hooks"])
    assert spec.env["CLAUDE_MEM_FIRST_SEARCH_TOOL"] == "mcp__mcp-search__search"
    assert spec.env["CLAUDE_MEM_FIRST_SEARCH_SENTINEL"].endswith("first-search-called")
    assert spec.env["CLAUDE_MEM_ENFORCE_FIRST_SEARCH"] == "1"
    assert spec.bare is False


def test_runtime_env_exposes_user_local_bin_for_uvx(tmp_path, monkeypatch):
    plugin_root = _fake_plugin(tmp_path / "vendor")
    monkeypatch.setenv(CONFIG["plugin_dir_env"], str(plugin_root))
    monkeypatch.setenv(CONFIG["observer_api_key_env"], "test-key")
    existing = os.pathsep.join(("/usr/bin", str(Path.home() / ".local" / "bin")))
    monkeypatch.setenv("PATH", existing)

    adapter = ClaudeMemAdapter(tmp_path / "staging", tmp_path / "base.md")
    runtime = adapter._runtime_env("namespace", tmp_path / "data")
    path_parts = runtime["PATH"].split(os.pathsep)

    assert path_parts[0] == str(Path.home() / ".local" / "bin")
    assert path_parts.count(str(Path.home() / ".local" / "bin")) == 1
    assert path_parts[1] == str(Path.home() / ".bun" / "bin")
    assert path_parts.count(str(Path.home() / ".bun" / "bin")) == 1
    assert "/usr/bin" in path_parts


def test_bulk_backfill_patch_isolated_from_the_official_plugin(tmp_path):
    plugin_root = _fake_plugin(tmp_path / "vendor")
    worker = plugin_root / "plugin" / "scripts" / "worker-service.cjs"
    marker = "async backfillKind(e,r,n,s){old}async backfillObservations"
    worker.write_text("prefix" + marker + "suffix", encoding="utf-8")

    adapter = ClaudeMemAdapter(tmp_path / "staging", tmp_path / "base.md")
    prepared = adapter._bulk_backfill_plugin_root(plugin_root / "plugin", "namespace")

    assert prepared == tmp_path / "staging" / "namespace" / "claude-mem-prep-plugin"
    assert marker in worker.read_text(encoding="utf-8")
    patched = (prepared / "scripts" / "worker-service.cjs").read_text(encoding="utf-8")
    assert "old" not in patched
    assert "this.addDocuments(l)" in patched


def test_session_lifecycle_starts_and_stops_the_isolated_worker(tmp_path, monkeypatch):
    plugin_root = _fake_plugin(tmp_path / "vendor")
    monkeypatch.setenv(CONFIG["plugin_dir_env"], str(plugin_root))
    monkeypatch.setenv(CONFIG["observer_api_key_env"], "test-key")
    adapter = ClaudeMemAdapter(tmp_path / "staging", tmp_path / "base.md")
    calls = []
    monkeypatch.setattr(
        adapter,
        "_start_worker",
        lambda plugin, data, namespace: calls.append(("start", plugin, data, namespace)),
    )
    monkeypatch.setattr(
        adapter,
        "_stop_worker",
        lambda plugin, data, namespace: calls.append(("stop", plugin, data, namespace)),
    )

    adapter.prepare_for_session("cell")
    adapter.cleanup_after_session("cell")

    assert [call[0] for call in calls] == ["start", "stop"]
    assert all(call[1] == plugin_root / "plugin" for call in calls)
    assert all(call[3] == "cell" for call in calls)


def test_namespace_copy_retries_a_disappearing_sqlite_journal(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "chroma.sqlite3").write_bytes(b"database")
    journal = str(source / "chroma.sqlite3-journal")
    real_copytree = shutil.copytree
    calls = 0

    def flaky_copytree(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise shutil.Error(
                [(journal, str(target / "chroma.sqlite3-journal"), "[Errno 2] No such file or directory")]
            )
        return real_copytree(*args, **kwargs)

    monkeypatch.setattr(shutil, "copytree", flaky_copytree)
    ClaudeMemAdapter._copy_stable_tree(source, target, lambda _directory, _names: set())

    assert calls == 2
    assert (target / "chroma.sqlite3").read_bytes() == b"database"


def test_chroma_sync_state_requires_empty_pending_sets(tmp_path):
    state = tmp_path / "chroma-sync-state.json"
    state.write_text(
        json.dumps(
            {
                "claude_mem": {
                    "observations": 3,
                    "pending": {"observations": [2], "summaries": [], "prompts": []},
                }
            }
        ),
        encoding="utf-8",
    )
    assert not ClaudeMemAdapter._chroma_sync_complete(tmp_path, 3)

    state.write_text(
        json.dumps(
            {
                "claude_mem": {
                    "observations": 3,
                    "pending": {"observations": [], "summaries": [], "prompts": []},
                }
            }
        ),
        encoding="utf-8",
    )
    assert ClaudeMemAdapter._chroma_sync_complete(tmp_path, 3)


def test_reuses_only_a_fresh_verified_fixture_without_import(tmp_path, monkeypatch):
    adapter = ClaudeMemAdapter(tmp_path / "staging", tmp_path / "base.md")
    cache_root = tmp_path / "fixtures"
    material = {"schema": 1, "corpus_sha256": "corpus", "plugin_tree_sha256": "plugin"}
    fixture = cache_root / "fixture-key"
    data = fixture / "claude-mem-data"
    data.mkdir(parents=True)
    (data / "chroma-sync-state.json").write_text(
        json.dumps({"claude_mem": {"observations": 2, "pending": {"observations": [], "summaries": [], "prompts": []}}}),
        encoding="utf-8",
    )
    (fixture / "fixture.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "fingerprint": material,
                "created_at_epoch": time.time(),
                "observations": 2,
                "items_stored": 2,
                "verification_query": "fixture query",
                "search_start": "2026-09-08T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(adapter, "_start_worker", lambda *args: calls.append("start"))
    monkeypatch.setattr(adapter, "_wait_for_chroma_sync", lambda *args: calls.append("wait"))
    request_timeouts = []

    def request(*args, **kwargs):
        request_timeouts.append(kwargs.get("timeout"))
        return {"observations": [{}]}

    monkeypatch.setattr(adapter, "_request", request)

    report = adapter._reuse_fixture(
        cache_root,
        "fixture-key",
        material,
        type("Corpus", (), {"sessions": {"one.md": "hash", "two.md": "hash"}})(),
        tmp_path / "plugin",
        tmp_path / "staging" / "run" / "claude-mem-data",
    )

    assert report is not None
    assert any("reused a verified immutable Claude-Mem fixture" in note for note in report.notes)
    assert calls == ["start", "wait"]
    assert request_timeouts == [180.0]


def test_frozen_config_contains_the_release_pin_and_no_credentials():
    text = (REPO / "adapters" / "claude_mem" / "config.frozen.json").read_text(encoding="utf-8")
    assert CONFIG["plugin_tag"] == "v13.24.0"
    assert len(CONFIG["plugin_commit"]) == 40
    assert "test-key" not in text


def test_opt_in_first_search_guard_denies_file_tools_until_search(tmp_path):
    node = shutil.which("node")
    if not node:
        return
    wrapper = REPO / "adapters" / "claude_mem" / "hook_wrapper.js"
    ledger = tmp_path / "ledger.jsonl"
    sentinel = tmp_path / "first-search-called"
    env = {
        **os.environ,
        "CLAUDE_MEM_ENFORCE_FIRST_SEARCH": "1",
        "CLAUDE_MEM_FIRST_SEARCH_SENTINEL": str(sentinel),
        "CLAUDE_MEM_FIRST_SEARCH_TOOL": "mcp__mcp-search__search",
        "CLAUDE_MEM_HOOK_LEDGER": str(ledger),
    }
    argv = base64.b64encode(json.dumps(["-e", ""]).encode()).decode()

    def call(tool_name):
        return subprocess.run(
            [node, str(wrapper), "PreToolUse", argv],
            input=json.dumps({"session_id": "session", "tool_name": tool_name}),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    denied = call("Read")
    assert denied.returncode == 0
    assert json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert not sentinel.exists()

    searched = call("mcp__mcp-search__search")
    assert searched.returncode == 0
    assert sentinel.exists()
    assert call("Read").returncode == 0
