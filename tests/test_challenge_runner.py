"""Tests for the isolated per task Docker command builder."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness.challenge_pack import (
    build_execution_plan,
    load_private_pack,
    load_submission,
)
from harness.challenge_runner import (
    ChallengeRunnerError,
    _best_effort_remove_container,
    build_adapter_service_argv,
    build_docker_argv,
)


def _pack(tmp_path: Path):
    root = tmp_path / "pack"
    root.mkdir()
    for relative in (
        "corpus/manifest.json",
        "fixtures/task-a/README.md",
        "prompts/task-a.txt",
        "checkers/task-a/checker.py",
        "oracles/task-a/input.txt",
        "references/task-a/informed.py",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder", encoding="utf-8")
    (root / "pack.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "amb-private-evaluation-pack",
                "visibility": "private",
                "pack_id": "challenge-test-001",
                "source_public_commit": "abc123",
                "scoring_version": "score-1",
                "corpus": "corpus",
                "tasks": [
                    {
                        "task_id": "task-a",
                        "fixture": "fixtures/task-a",
                        "prompt": "prompts/task-a.txt",
                        "checker": "checkers/task-a/checker.py",
                        "oracle": "oracles/task-a",
                        "reference": "references/task-a",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return load_private_pack(root)


def test_container_cleanup_ignores_docker_timeout(monkeypatch: pytest.MonkeyPatch):
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr("harness.challenge_runner.subprocess.run", raise_timeout)

    _best_effort_remove_container("docker", "amb-task")


def _submission(tmp_path: Path, network: str = "none"):
    path = tmp_path / "submission.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "kind": "amb-challenge-submission",
                "submission_id": "entry-a",
                "image": "registry.example/amb/entry@sha256:" + "a" * 64,
                "source_revision": "source-abc123",
                "adapter_api": "amb-challenge-adapter-v1",
                "config_sha256": "b" * 64,
                "network": network,
                "entrypoint": ["/usr/local/bin/amb-entry", "serve"],
            }
        ),
        encoding="utf-8",
    )
    return load_submission(path)


def test_docker_command_is_per_task_and_never_mounts_private_checker_inputs(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = _submission(tmp_path)
    plan = build_execution_plan(pack, submission, "task-a")
    argv = build_docker_argv(pack, plan, tmp_path / "output", container_name="amb-test")
    command = " ".join(argv)
    assert "--pull=never" in command
    assert "--network=none" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "no-new-privileges:true" in command
    assert ",rw" not in command
    assert "/challenge/task" in command
    assert "/challenge/prompt.txt" in command
    assert "checkers" not in command
    assert "oracles" not in command
    assert "references" not in command


def test_output_root_cannot_be_inside_pack(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = _submission(tmp_path)
    plan = build_execution_plan(pack, submission, "task-a")
    with pytest.raises(ChallengeRunnerError, match="private pack"):
        build_docker_argv(pack, plan, pack.root / "output", container_name="amb-test")


def test_model_only_requires_evaluator_proxy(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = _submission(tmp_path, network="model-only")
    plan = build_execution_plan(pack, submission, "task-a")
    with pytest.raises(ChallengeRunnerError, match="model proxy"):
        build_docker_argv(pack, plan, tmp_path / "output", container_name="amb-test")


def test_model_only_mounts_only_the_evaluator_proxy(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = _submission(tmp_path, network="model-only")
    plan = build_execution_plan(pack, submission, "task-a")
    proxy = tmp_path / "model-proxy.sock"
    proxy.write_text("proxy placeholder", encoding="utf-8")
    argv = build_docker_argv(
        pack,
        plan,
        tmp_path / "output",
        container_name="amb-test",
        model_proxy_socket=proxy,
    )
    command = " ".join(argv)
    assert "--network=none" in command
    assert f"src={proxy.resolve()}" in command
    assert "AMB_MODEL_PROXY_SOCKET=/challenge/model-proxy.sock" in command


def test_sidecar_command_mounts_no_task_prompt_or_fixture(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = _submission(tmp_path)
    plan = build_execution_plan(pack, submission, "task-a")
    argv = build_adapter_service_argv(
        pack,
        plan,
        tmp_path / "output",
        tmp_path / "runtime",
        container_name="amb-sidecar-test",
    )
    command = " ".join(argv)
    assert "/challenge/corpus" in command
    assert "/challenge/runtime" in command
    assert "/challenge/output" not in command
    assert "/challenge/task" not in command
    assert "/challenge/prompt.txt" not in command
    assert "fixtures" not in command
    assert "prompts" not in command
    assert "checkers" not in command
    assert "oracles" not in command
    assert "references" not in command
    assert "AMB_ADAPTER_SOCKET=/challenge/runtime/adapter.sock" in command


def test_sidecar_rejects_overlapping_output_and_runtime_roots(tmp_path: Path):
    pack = _pack(tmp_path)
    submission = _submission(tmp_path)
    plan = build_execution_plan(pack, submission, "task-a")
    with pytest.raises(ChallengeRunnerError, match="must not overlap"):
        build_adapter_service_argv(
            pack,
            plan,
            tmp_path / "shared",
            tmp_path / "shared" / "runtime",
            container_name="amb-sidecar-test",
        )
