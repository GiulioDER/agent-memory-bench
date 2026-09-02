"""Cachly adapter tests, without contacting the vendor service."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters.cachly.adapter import CachlyAdapter
from harness import instructions
from harness.adapters.base import CorpusManifest
from harness.instructions import APPENDIX_MAX_BYTES

REPO = Path(__file__).resolve().parents[1]
CONFIG = json.loads(
    (REPO / "adapters" / "cachly" / "config.frozen.json").read_text(encoding="utf-8")
)


@pytest.fixture()
def base_prompt(tmp_path):
    path = tmp_path / "claude_md.md"
    path.write_text("# Fixture README\n\nStatic half, shared by every arm.\n", encoding="utf-8")
    return path


@pytest.fixture()
def adapter(tmp_path, base_prompt, monkeypatch):
    monkeypatch.setenv(CONFIG["instance_id_env"], "instance-for-tests")
    monkeypatch.setenv(CONFIG["api_key_env"], "key-for-tests")
    monkeypatch.setenv(CONFIG["bulk_ingest_command_env"], json.dumps(["vendor-loader"]))
    return CachlyAdapter(tmp_path / "staging", base_prompt)


@pytest.fixture()
def corpus(tmp_path):
    root = tmp_path / "corpus"
    path = root / "sessions" / "task" / "p01.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text('{"role":"user","content":"why does CI fail?","ts":1}\n', "utf-8")
    rel = "sessions/task/p01.jsonl"
    (root / "manifest.json").write_text(
        json.dumps({"sessions": {rel: hashlib.sha256(path.read_bytes()).hexdigest()}}),
        encoding="utf-8",
    )
    return CorpusManifest.load(root)


def test_the_arm_is_registered_in_runner_and_abstention_rosters():
    from scripts import abstention, pilot

    assert "cachly" in pilot.ARMS
    assert "cachly" in pilot.MEMORY_ARMS
    assert "cachly" in pilot.SELF_INGESTING_ARMS
    assert "cachly" in abstention.MEMORY_ARMS


def test_adapter_for_builds_cachly(tmp_path, base_prompt):
    from scripts import pilot

    built = pilot.adapter_for("cachly", {"claude_md": base_prompt}, tmp_path, {"cachly": ""})
    assert isinstance(built, CachlyAdapter)


def test_the_arm_carries_the_shared_protocol_and_capped_appendix():
    text = CachlyAdapter.shared_instruction()
    instructions.assert_shared_protocol({"cachly": text})
    appendix = (REPO / "adapters" / "cachly" / "instruction_appendix.md").read_bytes()
    assert 0 < len(appendix) <= APPENDIX_MAX_BYTES


def test_the_search_sentence_names_the_primary_tool():
    assert f"{CONFIG['tool_prefix']}smart_recall" in CONFIG["search_sentence"]
    assert "smart_recall" in CONFIG["allowed_tools"]


def test_build_uses_the_exact_pinned_stdio_package(adapter, tmp_path):
    spec = adapter.build_for_task(tmp_path / "session", "ns", "task", "do the task")
    config = json.loads(Path(spec.mcp_config).read_text(encoding="utf-8"))
    server = config["mcpServers"][CONFIG["server_name"]]
    assert server["command"] == ("npx.cmd" if os.name == "nt" else "npx")
    assert server["args"] == ["-y", CONFIG["package_pin"]]
    assert server["env"][CONFIG["instance_id_env"]] == "instance-for-tests"
    assert server["env"][CONFIG["api_key_env"]] == "key-for-tests"
    assert "PATH" in server["env"]
    assert spec.extra_allowed_tools == tuple(
        f"{CONFIG['tool_prefix']}{tool}" for tool in CONFIG["allowed_tools"]
    )


def test_windows_npx_normalization_keeps_other_commands_unchanged():
    assert CachlyAdapter._windows_npx_name("npx") == ("npx.cmd" if os.name == "nt" else "npx")
    assert CachlyAdapter._windows_npx_name("vendor-loader") == "vendor-loader"


def test_missing_credentials_are_refused_before_a_server_config_is_built(
    tmp_path, base_prompt, monkeypatch
):
    monkeypatch.setenv(CONFIG["instance_id_env"], "instance-for-tests")
    monkeypatch.delenv(CONFIG["api_key_env"], raising=False)
    monkeypatch.delenv(CONFIG["jwt_env"], raising=False)
    adapter = CachlyAdapter(tmp_path / "staging", base_prompt)
    with pytest.raises(RuntimeError, match="CACHLY_API_KEY|CACHLY_JWT"):
        adapter.build(tmp_path / "session", "ns")


def test_bulk_ingest_passes_the_manifest_contract_and_reports_counts(
    adapter, corpus, monkeypatch
):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["env"] = kwargs["env"]
        return SimpleNamespace(
            returncode=0,
            stdout='loader progress\n{"namespace":"ns","sessions_offered":1,"items_stored":7}\n',
            stderr="",
        )

    monkeypatch.setattr("adapters.cachly.adapter.subprocess.run", fake_run)
    report = adapter.ingest(corpus, "ns")
    assert seen["command"] == ["vendor-loader"]
    assert seen["env"]["AMB_CACHLY_CORPUS_ROOT"] == str(corpus.root.resolve())
    assert seen["env"]["AMB_CACHLY_CORPUS_MANIFEST"] == str(
        (corpus.root / "manifest.json").resolve()
    )
    assert seen["env"]["AMB_CACHLY_EXPECTED_SESSIONS"] == "1"
    assert report.items_stored == 7
    assert report.sessions_offered == 1
    assert report.wall_time_ms is not None


def test_bulk_ingest_refuses_a_loader_that_reports_the_wrong_corpus(
    adapter, corpus, monkeypatch
):
    monkeypatch.setattr(
        "adapters.cachly.adapter.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout='{"sessions_offered":2,"items_stored":7}\n',
            stderr="",
        ),
    )
    with pytest.raises(RuntimeError, match="contains 1"):
        adapter.ingest(corpus, "ns")


def test_missing_bulk_loader_is_refused(adapter, corpus, monkeypatch):
    monkeypatch.delenv(CONFIG["bulk_ingest_command_env"], raising=False)
    with pytest.raises(RuntimeError, match=CONFIG["bulk_ingest_command_env"]):
        adapter.ingest(corpus, "ns")


def test_frozen_config_contains_no_credentials_or_machine_values():
    text = (REPO / "adapters" / "cachly" / "config.frozen.json").read_text(encoding="utf-8")
    assert "key-for-tests" not in text
    assert "instance-for-tests" not in text
    for key in ("instance_id_env", "api_key_env", "jwt_env", "api_url_env"):
        assert CONFIG[key].isupper()
