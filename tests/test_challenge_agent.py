"""Tests for the bounded fixed evaluator agent command."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from harness.challenge_agent import ChallengeAgentError, run_fixed_agent_command


def _context(tmp_path: Path):
    output = tmp_path / "output"
    output.mkdir()
    return SimpleNamespace(
        task_id="task-a",
        fixture=tmp_path / "fixture",
        prompt=tmp_path / "prompt.txt",
        output=output,
        adapter=SimpleNamespace(socket_path=tmp_path / "adapter.sock"),
    )


def test_fixed_agent_command_receives_only_explicit_task_environment(tmp_path: Path):
    context = _context(tmp_path)
    script = tmp_path / "agent.py"
    script.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "expected = {\n"
        "'AMB_CHALLENGE_API': 'amb-challenge-adapter-v1',\n"
        "'AMB_AGENT_PROTOCOL': 'search-only-adapter',\n"
        "'AMB_TASK_ID': 'task-a',\n"
        f"'AMB_TASK_FIXTURE': {str(context.fixture)!r},\n"
        f"'AMB_TASK_PROMPT': {str(context.prompt)!r},\n"
        f"'AMB_TASK_OUTPUT': {str(context.output)!r},\n"
        f"'AMB_ADAPTER_SOCKET': {str(context.adapter.socket_path)!r},\n"
        "}\n"
        "assert all(os.environ.get(k) == v for k, v in expected.items())\n"
        "Path(os.environ['AMB_TASK_OUTPUT'], 'answer.txt').write_text('ok')\n",
        encoding="utf-8",
    )
    result = run_fixed_agent_command(
        ["python", str(script)],
        context,
        timeout_seconds=10,
        extra_env={"AMB_MODEL_NAME": "fixed-model"},
    )
    assert result.ok
    assert (context.output / "answer.txt").read_text() == "ok"


def test_fixed_agent_does_not_receive_ambient_credentials(tmp_path: Path, monkeypatch):
    context = _context(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    result = run_fixed_agent_command(
        ["python", "-c", "import os; assert 'OPENAI_API_KEY' not in os.environ"],
        context,
        timeout_seconds=10,
    )
    assert result.ok


def test_fixed_agent_command_rejects_empty_command(tmp_path: Path):
    with pytest.raises(ChallengeAgentError, match="non empty"):
        run_fixed_agent_command([], _context(tmp_path))


def test_fixed_agent_command_cannot_override_task_identity(tmp_path: Path):
    with pytest.raises(ChallengeAgentError, match="reserved variables"):
        run_fixed_agent_command(
            ["python", "-c", "pass"],
            _context(tmp_path),
            extra_env={"AMB_TASK_ID": "other-task"},
        )


@pytest.mark.parametrize("timeout_seconds", [True, "nan", float("nan"), float("inf")])
def test_fixed_agent_command_rejects_invalid_timeout(tmp_path: Path, timeout_seconds):
    with pytest.raises(ChallengeAgentError, match="finite and positive"):
        run_fixed_agent_command(
            ["python", "-c", "pass"],
            _context(tmp_path),
            timeout_seconds=timeout_seconds,
        )
