"""Claude-Mem adapter tests that do not start a vendor worker or call a model."""

from __future__ import annotations

import json
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
                    "PreToolUse": [{"hooks": [{"type": "command", "command": "file"}]}],
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
    instructions.assert_shared_protocol({"claude_mem": ClaudeMemAdapter.shared_instruction()})
    appendix = (REPO / "adapters" / "claude_mem" / "instruction_appendix.md").read_bytes()
    assert 0 < len(appendix) <= APPENDIX_MAX_BYTES


def test_build_uses_the_pinned_official_server_and_hooks(tmp_path, monkeypatch):
    plugin_root = _fake_plugin(tmp_path / "vendor")
    base_prompt = tmp_path / "base.md"
    base_prompt.write_text("# Fixture\n", encoding="utf-8")
    monkeypatch.setenv(CONFIG["plugin_dir_env"], str(plugin_root))
    monkeypatch.setenv(CONFIG["observer_api_key_env"], "test-key")

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
    settings = json.loads((Path(spec.config_dir) / "settings.json").read_text(encoding="utf-8"))
    assert set(CONFIG["required_hooks"]).issubset(settings["hooks"])
    assert "SessionStartWorker" in json.dumps(settings)
    assert spec.bare is False


def test_frozen_config_contains_the_release_pin_and_no_credentials():
    text = (REPO / "adapters" / "claude_mem" / "config.frozen.json").read_text(encoding="utf-8")
    assert CONFIG["plugin_tag"] == "v13.24.0"
    assert len(CONFIG["plugin_commit"]) == 40
    assert "test-key" not in text
