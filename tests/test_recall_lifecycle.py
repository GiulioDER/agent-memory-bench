from __future__ import annotations

import base64
from contextlib import contextmanager
from pathlib import Path

import pytest

from adapters.recall.adapter import RecallAdapter
from harness.lifecycle import load_lifecycle_manifest

ROOT = Path(__file__).resolve().parents[1]


class FakeMcp:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def call(self, name, arguments):
        self.calls.append((name, arguments))
        return self.payload


def _adapter(tmp_path):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("# prompt\n", encoding="utf-8")
    return RecallAdapter(tmp_path / "staging", prompt)


def _event_and_content():
    _, events, _ = load_lifecycle_manifest(ROOT / "capabilities" / "lifecycle-temporal.json")
    event = events[0]
    return event, (ROOT / "corpus" / event.source_path).read_bytes()


def test_recall_lifecycle_uses_bounded_mcp_ingest(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    fake = FakeMcp(
        {"files": 1, "chunks": 2, "skipped": 0, "message": "Built and activated generation"}
    )

    @contextmanager
    def client(_namespace):
        yield fake

    monkeypatch.setattr(adapter, "_lifecycle_mcp", client)
    event, content = _event_and_content()

    report = adapter.ingest_event("isolated-lifecycle", event, content)

    assert report.outcome == "inserted"
    assert report.indexed is True
    assert report.deduplicated is False
    assert report.visibility_boundary.startswith("fresh recall MCP")
    name, arguments = fake.calls[0]
    assert name == "recall_ingest"
    uploaded = arguments["files"][0]
    assert uploaded["name"] == "sessions__xs-evolve-lease__p01.md"
    rendered = base64.b64decode(uploaded["content_b64"]).decode("utf-8")
    assert rendered.startswith("---\nvalid_from: 2026-04-12\n---\n")
    assert "renew every 90 seconds" in rendered
    assert arguments["category"] == "memory"
    assert len(arguments["idempotency_key"]) == 64


def test_recall_lifecycle_records_server_deduplication(tmp_path, monkeypatch):
    """Mutation proof target: deduplication must not be reported as a fresh replay index.

    The production symbol under test is ``RecallAdapter.ingest_event``'s repeated idempotency
    branch. A mutation that removes ``indexed, deduplicated = False, True`` makes the final
    ``report.indexed is False`` assertion fail, rather than merely changing setup or collection.
    """
    adapter = _adapter(tmp_path)
    fake = FakeMcp(
        {"files": 1, "chunks": 2, "skipped": 0, "message": "Built and activated generation"}
    )

    @contextmanager
    def client(_namespace):
        yield fake

    monkeypatch.setattr(adapter, "_lifecycle_mcp", client)
    _, events, _ = load_lifecycle_manifest(ROOT / "capabilities" / "lifecycle-temporal.json")
    initial = events[0]
    replay = events[-1]
    content = (ROOT / "corpus" / initial.source_path).read_bytes()
    adapter.ingest_event("isolated-lifecycle", initial, content)
    fake.payload = {
        "files": 1,
        "chunks": 2,
        "skipped": 0,
        "message": "Built and activated generation",
    }

    report = adapter.ingest_event("isolated-lifecycle", replay, content)

    assert report.outcome == "deduplicated"
    assert report.indexed is False
    assert report.deduplicated is True
    assert report.items_stored == 2


def test_recall_lifecycle_rejects_a_non_live_generation(tmp_path, monkeypatch):
    """Mutation proof target: a completed build must not be mistaken for serving visibility.

    The production symbol under test is the activation guard in ``RecallAdapter.ingest_event``.
    A mutation that removes the ``"not live"`` or ``"activated"`` guard makes the assertion below
    fail with ``pytest.raises``; timeout or fixture failure would not satisfy this proof.
    """
    adapter = _adapter(tmp_path)
    fake = FakeMcp(
        {
            "files": 1,
            "chunks": 2,
            "skipped": 0,
            "message": "Built and validated but not live",
        }
    )

    @contextmanager
    def client(_namespace):
        yield fake

    monkeypatch.setattr(adapter, "_lifecycle_mcp", client)
    event, content = _event_and_content()

    with pytest.raises(RuntimeError, match="activated generation"):
        adapter.ingest_event("isolated-lifecycle", event, content)


def test_recall_lifecycle_ssh_keeps_native_ssh_environment(tmp_path, monkeypatch):
    """Mutation proof target: the lifecycle SSH child must retain native SSH configuration.

    The production symbol under test is the SSH environment construction in
    ``RecallAdapter._lifecycle_mcp``. A mutation that restores the four variable allowlist makes
    ``SSH_AUTH_SOCK`` disappear and fails the assertion, while provider credentials remain absent.
    """
    adapter = _adapter(tmp_path)
    adapter.config["transport"] = "ssh"
    monkeypatch.setenv("RECALL_DSN", "postgresql://test")
    monkeypatch.setenv("AMB_RECALL_SSH_HOST", "test-host")
    monkeypatch.setenv("AMB_RECALL_REMOTE_ROOT", "/srv/recall")
    monkeypatch.setenv("AMB_RECALL_REMOTE_PYTHON", "/srv/recall/.venv/bin/python")
    monkeypatch.setenv("AMB_RECALL_REMOTE_ENV_FILE", "/srv/recall/.env")
    monkeypatch.setenv("SSH_AUTH_SOCK", "test-agent-socket")
    monkeypatch.setenv("VOYAGE_API_KEY", "test-provider-secret")

    captured = {}

    class Process:
        stdin = None
        stdout = None
        stderr = None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

    def popen(*args, **kwargs):
        captured.update(kwargs)
        return Process()

    monkeypatch.setattr("adapters.recall.adapter.subprocess.Popen", popen)
    monkeypatch.setattr("adapters.recall.adapter._LifecycleMcpClient.start", lambda self: None)

    with adapter._lifecycle_mcp("isolated-lifecycle"):
        pass

    assert captured["env"]["SSH_AUTH_SOCK"] == "test-agent-socket"
    assert "VOYAGE_API_KEY" not in captured["env"]
