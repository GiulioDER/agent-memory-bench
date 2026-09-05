"""Tests for evaluator sequencing and the fixed sidecar client."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from harness.challenge_evaluator import (
    ChallengeAdapterClient,
    ChallengeEvaluatorError,
    evaluate_submission,
)
from harness.challenge_protocol import ADAPTER_API


def test_sidecar_client_sends_fixed_task_scoped_requests(monkeypatch, tmp_path: Path):
    requests: list[tuple[str, str, dict]] = []

    def fake_request(socket_path, request_id, method, params):
        requests.append((request_id, method, params))
        return {"api": ADAPTER_API, "id": request_id, "ok": True, "result": {"ready": True}}

    monkeypatch.setattr("harness.challenge_evaluator.request_unix_socket", fake_request)
    client = ChallengeAdapterClient(tmp_path / "adapter.sock", "task-a")
    assert client.health() == {"ready": True}
    assert client.search("find this", limit=3) == {"ready": True}
    assert client.reset() == {"ready": True}
    assert requests == [
        ("task-a-1", "health", None),
        ("task-a-2", "search", {"task_id": "task-a", "query": "find this", "limit": 3}),
        ("task-a-3", "reset", {"task_id": "task-a"}),
    ]


def test_sidecar_client_turns_protocol_error_into_evaluator_error(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "harness.challenge_evaluator.request_unix_socket",
        lambda *_args: {
            "api": ADAPTER_API,
            "id": "task-a-1",
            "ok": False,
            "error": {"code": "bad_request"},
        },
    )
    with pytest.raises(ChallengeEvaluatorError, match="adapter health failed"):
        ChallengeAdapterClient(tmp_path / "adapter.sock", "task-a").health()


def test_sidecar_client_enforces_fixed_call_budget(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "harness.challenge_evaluator.request_unix_socket",
        lambda _socket, request_id, _method, _params: {
            "api": ADAPTER_API,
            "id": request_id,
            "ok": True,
            "result": {"ready": True},
        },
    )
    client = ChallengeAdapterClient(tmp_path / "adapter.sock", "task-a", max_calls=1)
    assert client.health() == {"ready": True}
    with pytest.raises(ChallengeEvaluatorError, match="call budget"):
        client.health()
    assert client._sequence == 1


def test_evaluator_hides_private_task_metadata_and_checks_after_sidecar(monkeypatch, tmp_path: Path):
    fixture = tmp_path / "fixture.json"
    prompt = tmp_path / "prompt.md"
    checker = tmp_path / "checker.py"
    oracle = tmp_path / "oracle"
    fixture.write_text("{}", encoding="utf-8")
    prompt.write_text("Answer", encoding="utf-8")
    checker.write_text("", encoding="utf-8")
    oracle.mkdir()
    task = SimpleNamespace(
        task_id="task-a",
        fixture=fixture,
        prompt=prompt,
        checker=checker,
        oracle=oracle,
        reference=None,
    )
    pack = SimpleNamespace(tasks=(task,), root=tmp_path / "pack")
    pack.root.mkdir()
    submission = SimpleNamespace(submission_id="entry-a")
    events: list[str] = []

    class FakeHandle:
        socket_path = tmp_path / "adapter.sock"

        def wait_ready(self):
            events.append("health")

        def stop(self):
            events.append("stop")

    def fake_start(*_args, **_kwargs):
        events.append("start")
        return FakeHandle()

    monkeypatch.setattr("harness.challenge_evaluator.start_challenge_adapter", fake_start)
    monkeypatch.setattr(
        "harness.challenge_evaluator.ChallengeAdapterClient.reset",
        lambda _client: events.append("reset") or {"reset": True},
    )
    monkeypatch.setattr(
        "harness.challenge_evaluator.run_private_checker",
        lambda _task, output, timeout_s: (
            events.append(f"check:{output.name}"),
            SimpleNamespace(task_id="task-a", passed=True),
        )[1],
    )
    monkeypatch.setattr(
        "harness.challenge_evaluator.build_score_manifest",
        lambda _pack, _submission, _scores, public: {"public": public},
    )

    def agent_runner(context):
        events.append("agent")
        assert context.task_id == "task-a"
        assert context.fixture == fixture
        assert context.prompt == prompt
        assert context.output == tmp_path / "output" / "entry-a" / "task-a"
        assert not hasattr(context, "task")
        assert not hasattr(context, "checker")
        assert not hasattr(context, "oracle")
        assert not hasattr(context.adapter, "reset")
        assert not hasattr(context.adapter, "health")

    public, private = evaluate_submission(
        pack,
        submission,
        tmp_path / "output",
        tmp_path / "runtime",
        agent_runner,
    )

    assert events == ["start", "health", "reset", "agent", "stop", "check:task-a"]
    assert public == {"public": True}
    assert private == {"public": False}


def test_evaluator_rejects_private_pack_output_before_creating_directories(tmp_path: Path):
    pack_root = tmp_path / "pack"
    pack_root.mkdir()
    pack = SimpleNamespace(tasks=(), root=pack_root)
    submission = SimpleNamespace(submission_id="entry-a")
    output_root = pack_root / "output"

    with pytest.raises(ChallengeEvaluatorError, match="private pack"):
        evaluate_submission(
            pack,
            submission,
            output_root,
            tmp_path / "runtime",
            lambda _context: None,
        )
    assert not output_root.exists()


def test_evaluator_records_agent_failure_and_still_builds_manifests(monkeypatch, tmp_path: Path):
    task = SimpleNamespace(
        task_id="task-a",
        fixture=tmp_path / "fixture",
        prompt=tmp_path / "prompt",
        checker=tmp_path / "checker.py",
        oracle=tmp_path / "oracle",
        reference=tmp_path / "reference",
    )
    task.fixture.mkdir()
    task.prompt.write_text("Answer", encoding="utf-8")
    task.checker.write_text("", encoding="utf-8")
    task.oracle.mkdir()
    task.reference.mkdir()
    pack = SimpleNamespace(tasks=(task,), root=tmp_path / "pack")
    pack.root.mkdir()
    submission = SimpleNamespace(submission_id="entry-a")
    events: list[str] = []

    class FakeHandle:
        socket_path = tmp_path / "adapter.sock"

        def wait_ready(self):
            events.append("health")

        def stop(self):
            events.append("stop")

    monkeypatch.setattr(
        "harness.challenge_evaluator.start_challenge_adapter",
        lambda *_args, **_kwargs: events.append("start") or FakeHandle(),
    )
    monkeypatch.setattr(
        "harness.challenge_evaluator.ChallengeAdapterClient.reset",
        lambda _client: events.append("reset") or {"reset": True},
    )
    monkeypatch.setattr(
        "harness.challenge_evaluator.build_score_manifest",
        lambda _pack, _submission, scores, public: {
            "passed": scores[0].passed,
            "public": public,
        },
    )

    public, private = evaluate_submission(
        pack,
        submission,
        tmp_path / "output",
        tmp_path / "runtime",
        lambda _context: (_ for _ in ()).throw(RuntimeError("model timeout")),
    )

    assert events == ["start", "health", "reset", "stop"]
    assert public == {"passed": False, "public": True}
    assert private == {"passed": False, "public": False}
