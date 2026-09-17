"""Frozen wiring and behavior for official-017's pre-mutation checkpoint."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from adapters.recall_checkpoint.adapter import (
    RecallGraphFullToolsCheckpointAdapter,
    RecallGraphFullToolsCheckpointPlaceboAdapter,
)
from adapters.recall_checkpoint.hook import (
    build_checkpoint_query,
    is_mutation_candidate,
    parse_checkpoint_marker,
    run_checkpoint,
)
from harness.gate import AdmissionSignal, check_session
from harness.schema import SessionRecord
from scripts.validate_run_setup import check_premutation_checkpoint_pair

ROOT = Path(__file__).resolve().parents[1]
TASKS = (
    "ts-base36-id,ts-bom-merge,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,"
    "ts-mig-name,ts-schema-additive,ts-semver-pin,ts-tz-utc"
)
ARMS = (
    "recall_graph_fulltools_protocol,"
    "recall_graph_fulltools_checkpoint_placebo,"
    "recall_graph_fulltools_checkpoint"
)


def test_mutation_detector_waits_for_a_real_repository_change() -> None:
    assert not is_mutation_candidate("Bash", {"command": "ls && cat hashutil.py"})
    assert not is_mutation_candidate("Bash", {"command": "python -m pytest -q 2>/dev/null"})
    assert not is_mutation_candidate("Read", {"file_path": "validator.py"})
    assert is_mutation_candidate("Write", {"file_path": "rotate.py", "content": "x"})
    assert is_mutation_candidate("Edit", {"file_path": ".gitignore", "new_string": "dist2/"})
    assert is_mutation_candidate("Bash", {"command": "cat > merge.py <<'EOF'\npass\nEOF"})
    assert is_mutation_candidate("Bash", {"command": "python scripts/regen_golden.py"})
    assert is_mutation_candidate(
        "Bash", {"command": "python -c \"from pathlib import Path; Path('x').write_text('y')\""}
    )


def test_query_uses_task_pending_mutation_and_bounded_current_target(tmp_path: Path) -> None:
    target = tmp_path / "hashutil.py"
    target.write_text("def fast_hash(value):\n    return value[:8]\n", encoding="utf-8")
    query = build_checkpoint_query(
        task="Add a disk cache using a helper from hashutil.py.",
        tool_name="Edit",
        tool_input={
            "file_path": str(target),
            "old_string": "return response",
            "new_string": "key = fast_hash(resource_id)\nreturn response",
        },
        cwd=tmp_path,
    )
    assert "disk cache" in query
    assert "fast_hash" in query
    assert "return value[:8]" in query
    assert "prior project decisions" in query
    assert len(query) <= 4096


def test_placebo_denies_once_without_calling_memory(tmp_path: Path) -> None:
    sentinel = tmp_path / "done"
    payload = {
        "cwd": str(tmp_path),
        "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "rotate.py"), "content": "pass\n"},
    }
    first = run_checkpoint(
        payload,
        mode="placebo",
        task="Write rotate.py",
        sentinel=sentinel,
        broker_call=lambda _query: (_ for _ in ()).throw(AssertionError("memory called")),
    )
    assert first["hookSpecificOutput"]["permissionDecision"] == "deny"
    diagnostic = parse_checkpoint_marker(
        first["hookSpecificOutput"]["permissionDecisionReason"]
    )
    assert diagnostic["mode"] == "placebo"
    assert diagnostic["status"] == "placebo"
    assert sentinel.is_file()
    assert run_checkpoint(
        payload,
        mode="placebo",
        task="Write rotate.py",
        sentinel=sentinel,
        broker_call=lambda _query: {},
    ) is None


def test_treatment_injects_only_trusted_ok_hits(tmp_path: Path) -> None:
    payload = {
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "validator.py"), "new_string": "priority"},
    }

    def broker_call(_query: str) -> tuple[dict, str, float]:
        return (
            {
                "trust_state": "trusted",
                "abstained": False,
                "advice": "Use supported current evidence.",
                "hits": [
                    {
                        "source": "sessions__ts-schema-additive__p01.md",
                        "verdict": "ok",
                        "text": "priority is optional and defaults to normal",
                    },
                    {
                        "source": "sessions__stale__p01.md",
                        "verdict": "superseded",
                        "text": "priority is required",
                    },
                ],
            },
            "raw-result",
            12.5,
        )

    output = run_checkpoint(
        payload,
        mode="treatment",
        task="Allow a priority field",
        sentinel=tmp_path / "done",
        broker_call=broker_call,
    )
    reason = output["hookSpecificOutput"]["permissionDecisionReason"]
    assert "optional and defaults to normal" in reason
    assert "priority is required" not in reason
    diagnostic = parse_checkpoint_marker(reason)
    assert diagnostic["status"] == "ok"
    assert diagnostic["ok_hit_count"] == 1
    assert diagnostic["sources"] == ["sessions__ts-schema-additive__p01.md"]


def test_adapter_builds_identical_isolated_hook_surface_for_both_modes(
    tmp_path: Path, monkeypatch,
) -> None:
    prompt = tmp_path / "static.md"
    prompt.write_text("# project\n", encoding="utf-8")
    for name, value in {
        "RECALL_DSN": "postgresql://example.invalid/recall",
        "AMB_RECALL_SSH_HOST": "example.invalid",
        "AMB_RECALL_REMOTE_ROOT": "/srv/recall",
        "AMB_RECALL_REMOTE_PYTHON": "/srv/recall/.venv/bin/python",
        "AMB_RECALL_REMOTE_ENV_FILE": "/srv/recall/.env",
    }.items():
        monkeypatch.setenv(name, value)
    treatment = RecallGraphFullToolsCheckpointAdapter(tmp_path / "stage", prompt)
    placebo = RecallGraphFullToolsCheckpointPlaceboAdapter(tmp_path / "stage", prompt)
    t_spec = treatment.build_for_task(
        tmp_path / "treatment", "tenant", "ts-schema-additive", "task prompt"
    )
    p_spec = placebo.build_for_task(
        tmp_path / "placebo", "tenant", "ts-schema-additive", "task prompt"
    )
    assert not t_spec.bare and not p_spec.bare
    assert t_spec.config_dir_digest == p_spec.config_dir_digest
    assert t_spec.extra_allowed_tools == p_spec.extra_allowed_tools
    assert len(t_spec.extra_allowed_tools) == 22
    assert t_spec.env["AMB_PUBLIC_CHECKPOINT_MODE"] == "treatment"
    assert p_spec.env["AMB_PUBLIC_CHECKPOINT_MODE"] == "placebo"
    settings = json.loads((Path(t_spec.config_dir) / "settings.json").read_text(encoding="utf-8"))
    assert settings["hooks"]["PreToolUse"][0]["matcher"] == "Write|Edit|Bash"


def test_official017_dry_run_builds_the_frozen_three_arm_grid() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.pilot",
            "--dry-run",
            "--run-id",
            "official-017-recall-premutation-checkpoint-paired-superseded",
            "--arms",
            ARMS,
            "--tasks",
            TASKS,
            "--seeds",
            "5",
            "--model",
            "deepseek/deepseek-v4-flash",
            "--memory-instruction",
            "premutation_checkpoint_paired",
            "--corpus-root",
            str(ROOT / "corpus" / "conditions" / "superseded" / "seed-1"),
            "--condition",
            "superseded",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "135 session(s)" in output
    assert "premutation_checkpoint_paired" in output
    assert "recall_graph_fulltools_checkpoint" in output


def test_setup_gate_freezes_the_checkpoint_contract() -> None:
    digest = "aae2f2cf6fe67cac3998b1692d9173ef9ae7edcbe3263053d36025e77f2dc7d8"
    env = {
        "memory_instruction": "premutation_checkpoint_paired",
        "shared_tool_prefix_groups": [list(ARMS.split(","))],
        "premutation_checkpoint_pair": {
            "arms": list(ARMS.split(",")),
            "instruction_bytes_by_arm": {arm: 3924 for arm in ARMS.split(",")},
            "instruction_sha256_by_arm": {arm: digest for arm in ARMS.split(",")},
            "checkpoint_k": 5,
            "query_limit_chars": 4096,
            "reason_limit_chars": 4800,
            "max_injected_hits": 3,
            "hit_text_limit_chars": 1200,
        },
        "adapters": {
            "recall_graph_fulltools_checkpoint_placebo": {
                "checkpoint_mode": "placebo",
                "checkpoint_hook_sha256": "hook",
            },
            "recall_graph_fulltools_checkpoint": {
                "checkpoint_mode": "treatment",
                "checkpoint_hook_sha256": "hook",
            },
        },
    }
    assert check_premutation_checkpoint_pair(env).ok is True
    env["premutation_checkpoint_pair"]["checkpoint_k"] = 10
    assert check_premutation_checkpoint_pair(env).ok is False


def _checkpoint_record(*, success: bool, diagnostic: dict | None) -> SessionRecord:
    metadata = {
        "session_tools": ["mcp__recall__recall_search"],
        "mcp_servers": [{"name": "recall", "status": "connected"}],
    }
    if diagnostic is not None:
        metadata["memory_checkpoint"] = diagnostic
    return SessionRecord(
        task_id="ts-schema-additive",
        arm="recall_graph_fulltools_checkpoint",
        success=success,
        metadata=metadata,
    )


def test_admission_refuses_a_successful_mutation_without_checkpoint() -> None:
    signal = AdmissionSignal(
        arm="recall_graph_fulltools_checkpoint",
        mcp_tool_prefixes=("mcp__recall__",),
        metadata={"checkpoint_mode": "treatment"},
    )
    verdict = check_session(_checkpoint_record(success=True, diagnostic=None), signal)
    assert not verdict.admitted
    assert any("successful repository mutation" in reason for reason in verdict.reasons)


def test_admission_keeps_failure_before_any_mutation() -> None:
    signal = AdmissionSignal(
        arm="recall_graph_fulltools_checkpoint",
        mcp_tool_prefixes=("mcp__recall__",),
        metadata={"checkpoint_mode": "treatment"},
    )
    verdict = check_session(_checkpoint_record(success=False, diagnostic=None), signal)
    assert verdict.admitted
    assert any("before reaching" in note for note in verdict.notes)


def test_admission_refuses_a_failed_session_that_mutated_before_checkpoint() -> None:
    signal = AdmissionSignal(
        arm="recall_graph_fulltools_checkpoint",
        mcp_tool_prefixes=("mcp__recall__",),
        metadata={"checkpoint_mode": "treatment"},
    )
    record = _checkpoint_record(success=False, diagnostic=None)
    record = replace(
        record,
        metadata={**record.metadata, "unguarded_mutation_count": 1},
    )
    verdict = check_session(record, signal)
    assert not verdict.admitted
    assert any("completed before" in reason for reason in verdict.reasons)


def test_admission_refuses_a_failed_checkpoint_receipt() -> None:
    signal = AdmissionSignal(
        arm="recall_graph_fulltools_checkpoint",
        mcp_tool_prefixes=("mcp__recall__",),
        metadata={"checkpoint_mode": "treatment"},
    )
    diagnostic = {
        "triggered": True,
        "mode": "treatment",
        "marker_count": 1,
        "status": "error",
        "query_sha256": "q",
        "result_sha256": "r",
        "injected_bytes": 100,
        "injected_sha256": "i",
    }
    verdict = check_session(_checkpoint_record(success=False, diagnostic=diagnostic), signal)
    assert not verdict.admitted
    assert any("retrieval or receipt failed" in reason for reason in verdict.reasons)
