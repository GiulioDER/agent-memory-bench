"""Make the repo root importable so `from harness import ...` works from any invocation dir."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


import pytest


@pytest.fixture
def recall_location(monkeypatch):
    """Placeholder host locations for tests that build a recall ArmSpec.

    The frozen config names these variables and never stores their values, because this tree is
    public and a host inventory is disclosure on its own. Before that change the values sat in
    `config.frozen.json`, so any test constructing an adapter got a real host for free -- these
    tests passed BECAUSE of the leak. The values below are deliberately unroutable: a test that
    starts genuinely reaching a host should fail loudly rather than reach somebody's machine.

    Not autouse. `tests/test_no_host_inventory.py` asserts an unset location REFUSES, and an
    autouse fixture would quietly satisfy the thing that test exists to check.
    """

    monkeypatch.setenv("RECALL_DSN", "postgresql://unused.invalid/bench")
    monkeypatch.setenv("AMB_RECALL_SSH_HOST", "unused.invalid")
    monkeypatch.setenv("AMB_RECALL_REMOTE_ROOT", "/nonexistent/bench")
    monkeypatch.setenv("AMB_RECALL_REMOTE_PYTHON", "/nonexistent/bench/.venv/bin/python")
    monkeypatch.setenv("AMB_RECALL_REMOTE_ENV_FILE", "/nonexistent/recall/.env")
