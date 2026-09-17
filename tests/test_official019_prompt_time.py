from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from adapters.recall_prompt_time.adapter import RecallGraphFullToolsPromptTimeAdapter
from harness import isolation
from harness.adapters.base import ArmSpec, CorpusManifest, IngestReport
from harness.claude_exec import ClaudeExecConfig, session_environment
from harness.privacy import public_receipt
from harness.schema import SessionRecord
from scripts import pilot
from scripts.pilot import prompt_time_hook_ledger
from scripts.validate_run_setup import check_prompt_time_pair


def test_prompt_time_pair_uses_identical_initial_protocol() -> None:
    arms = pilot.RECALL_PROMPT_TIME_PAIRED_ARMS
    texts = pilot.memory_instructions(pilot.PROMPT_TIME_PAIRED_VARIANT, arms)
    assert texts[arms[0]] == texts[arms[1]]
    assert "recall_reasoning_query" in texts[arms[0]]


def test_prompt_time_pair_rejects_roster_drift() -> None:
    with pytest.raises(ValueError, match="requires exactly"):
        pilot.validate_prompt_time_pair(
            pilot.PROMPT_TIME_PAIRED_VARIANT,
            (pilot.RECALL_GRAPH_FULLTOOLS_PROTOCOL_ARM,),
        )


def test_prompt_time_setup_validator_requires_the_frozen_pair() -> None:
    texts = pilot.memory_instructions(
        pilot.PROMPT_TIME_PAIRED_VARIANT,
        pilot.RECALL_PROMPT_TIME_PAIRED_ARMS,
    )
    hook = hashlib.sha256(
        (Path(__file__).parents[1] / "adapters" / "recall_prompt_time" / "hook.py")
        .read_bytes()
    ).hexdigest()
    env = {
        "memory_instruction": pilot.PROMPT_TIME_PAIRED_VARIANT,
        "prompt_time_pair": pilot.prompt_time_pair_metadata(texts),
        "shared_tool_prefix_groups": [list(pilot.RECALL_PROMPT_TIME_PAIRED_ARMS)],
        "adapters": {
            "recall_graph_fulltools_prompt_time": {
                "prompt_time_hook_source": "released recall_hooks.prompt_time",
                "prompt_time_hook_sha256": hook,
            }
        },
    }
    assert check_prompt_time_pair(env).ok is True
    env["prompt_time_pair"]["hook_max_hits"] = 4
    assert check_prompt_time_pair(env).ok is False


def test_prompt_time_ingest_renders_a_manifest_bound_snapshot(tmp_path, monkeypatch) -> None:
    corpus_root = tmp_path / "corpus"
    source = corpus_root / "sessions" / "task" / "p01.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text(
        '{"role":"user","content":"schema migration decision"}\n', encoding="utf-8"
    )
    corpus = CorpusManifest(
        root=corpus_root,
        sessions={"sessions/task/p01.jsonl": hashlib.sha256(source.read_bytes()).hexdigest()},
    )
    staging = tmp_path / "staging"
    base_prompt = tmp_path / "base.md"
    base_prompt.write_text("base\n", encoding="utf-8")
    adapter = RecallGraphFullToolsPromptTimeAdapter(staging, base_prompt)
    monkeypatch.setattr(
        "adapters.recall_graph_fulltools.adapter.RecallAdapter.ingest",
        lambda self, _corpus, namespace: IngestReport("recall", namespace, 1),
    )
    report = adapter.ingest(corpus, "run")
    snapshot = staging / "run" / "prompt-time-store"
    assert snapshot.is_dir()
    assert list(snapshot.glob("*.md"))
    manifest = json.loads((snapshot / "snapshot.manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"] == 1
    assert manifest["snapshot_digest"]
    assert "prompt-time snapshot rendered" in report.notes


def test_prompt_time_wrapper_fails_open_and_records_bounded_receipt(tmp_path) -> None:
    trace = tmp_path / "ledger.jsonl"
    wrapper = Path(__file__).parents[1] / "adapters" / "recall_prompt_time" / "hook.py"
    result = subprocess.run(
        [sys.executable, str(wrapper)],
        input='{"prompt":"a sufficiently long prompt for the hook"}',
        text=True,
        capture_output=True,
        env={
            "AMB_RECALL_PROMPT_TIME_TRACE": str(trace),
            "AMB_RECALL_HOOK_SOURCE_ROOT": str(tmp_path / "missing"),
        },
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""
    entry = json.loads(trace.read_text(encoding="utf-8"))
    assert entry["event"] == "UserPromptSubmit"
    assert entry["exit_code"] == 0
    assert entry["hook_error"] == "ModuleNotFoundError"
    assert entry["output_sha256"]


def test_prompt_time_trace_path_reaches_the_participant() -> None:
    config = ClaudeExecConfig(
        executable="/bin/true",
        env={"AMB_RECALL_PROMPT_TIME_TRACE": "/workspace/.amb-prompt-time-ledger.jsonl"},
        bare=False,
        strict_mcp_config=False,
    )
    assert session_environment(config)["AMB_RECALL_PROMPT_TIME_TRACE"] == (
        "/workspace/.amb-prompt-time-ledger.jsonl"
    )
    assert "AMB_RECALL_PROMPT_TIME_TRACE" in isolation._PUBLIC_ENV_NAMES


def test_prompt_time_ledger_reads_the_runtime_workspace(tmp_path) -> None:
    runtime_workspace = tmp_path / "runtime"
    runtime_workspace.mkdir()
    trace = runtime_workspace / ".amb-prompt-time-ledger.jsonl"
    trace.write_text(
        json.dumps({"event": "UserPromptSubmit", "exit_code": 0}) + "\n",
        encoding="utf-8",
    )
    spec = ArmSpec(
        arm="recall_graph_fulltools_prompt_time",
        metadata={
            "prompt_time_trace": str(tmp_path / "setup" / "prompt-time-ledger.jsonl"),
            "prompt_time_trace_relative": ".amb-prompt-time-ledger.jsonl",
        },
    )
    assert prompt_time_hook_ledger(spec, runtime_workspace) == (
        {"event": "UserPromptSubmit", "exit_code": 0},
    )


def test_prompt_time_diagnostics_are_publishable() -> None:
    receipt = public_receipt(
        SessionRecord(
            task_id="ts-base36-id",
            arm="recall_graph_fulltools_prompt_time",
            success=True,
            metadata={
                "prompt_time_hook": {
                    "event": "UserPromptSubmit",
                    "exit_code": 0,
                    "hook_error": None,
                    "injection_status": "context",
                    "output_bytes": 128,
                    "output_sha256": "output",
                    "source_count": 3,
                    "source_sha256": ["a", "b", "c"],
                },
                "prompt_time_snapshot_manifest": {
                    "corpus_fingerprint": "corpus",
                    "files": 4910,
                    "snapshot_digest": "snapshot",
                },
            },
        )
    )
    assert receipt["metadata"]["prompt_time_hook"]["source_count"] == 3
    assert receipt["metadata"]["prompt_time_snapshot_manifest"]["files"] == 4910


def test_prompt_time_build_copies_release_and_uses_container_paths(tmp_path, monkeypatch) -> None:
    corpus_root = tmp_path / "corpus"
    source = corpus_root / "sessions" / "task" / "p01.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text(
        '{"role":"user","content":"schema migration decision"}\n', encoding="utf-8"
    )
    corpus = CorpusManifest(
        root=corpus_root,
        sessions={"sessions/task/p01.jsonl": hashlib.sha256(source.read_bytes()).hexdigest()},
    )
    staging = tmp_path / "staging"
    base_prompt = tmp_path / "base.md"
    base_prompt.write_text("base\n", encoding="utf-8")
    adapter = RecallGraphFullToolsPromptTimeAdapter(staging, base_prompt)
    monkeypatch.setattr(
        "adapters.recall_graph_fulltools.adapter.RecallAdapter.ingest",
        lambda self, _corpus, namespace: IngestReport("recall", namespace, 1),
    )
    monkeypatch.setattr(
        "adapters.recall_graph_fulltools.adapter.RecallGraphFullToolsProtocolAdapter.build_for_task",
        lambda self, session_dir, namespace, task_id, user_input: ArmSpec(arm=self.name),
    )
    adapter.ingest(corpus, "run")
    source_root = Path(__file__).parents[2] / "recall"
    monkeypatch.setenv("AMB_RECALL_HOOK_SOURCE_ROOT", str(source_root))
    spec = adapter.build_for_task(tmp_path / "session", "run", "task", "prompt")
    config_dir = spec.config_dir
    assert config_dir is not None
    assert (config_dir / "recall_hooks" / "prompt_time.py").is_file()
    assert (config_dir / "prompt-time-store").is_dir()
    assert list((config_dir / "prompt-time-store").glob("*.md"))
    settings = json.loads((config_dir / "settings.json").read_text(encoding="utf-8"))
    command = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    assert command == '"/usr/local/bin/python" "/session/claude-config/prompt_time_hook.py"'
    hook_config_path = config_dir / "recall-hook.json"
    hook_config = json.loads(hook_config_path.read_text(encoding="utf-8"))
    hook_config["prompt_time"]["store"] = str(config_dir / "prompt-time-store")
    hook_config_path.write_text(json.dumps(hook_config), encoding="utf-8")
    sys.path.insert(0, str(config_dir))
    from recall_hooks.prompt_time import load_memos, rank

    memos = load_memos(config_dir / "prompt-time-store")
    assert memos
    assert "schema" in memos[0][2]
    assert "decision" in memos[0][2]
    assert rank(memos, "which schema migration decision was made", 3)
    hook_env = {"CLAUDE_CONFIG_DIR": str(config_dir)}
    wrapper = config_dir / "prompt_time_hook.py"
    result = subprocess.run(
        [sys.executable, str(wrapper)],
        input='{"prompt":"which schema migration decision was made"}',
        text=True,
        capture_output=True,
        env=hook_env,
        check=False,
    )
    assert result.returncode == 0
    assert '"hookSpecificOutput"' in result.stdout, (
        f"stdout={result.stdout!r} stderr={result.stderr!r} "
        f"trace={(config_dir / 'prompt-time-ledger.jsonl').read_text(encoding='utf-8')!r}"
    )
