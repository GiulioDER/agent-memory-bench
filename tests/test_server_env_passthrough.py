"""The child environment must carry the credential a HOSTED embedder needs.

`RecallAdapter._server_env` builds the entire environment for the search subprocess and the MCP
server: the block REPLACES the parent environment rather than extending it. Its passthrough list
was written when the embedder was a local model that needed no credential, and nothing re-checked
it when the frozen config moved to `voyage:voyage-4`.

The cost of that gap, measured 2026-08-31: the `recall_prefetch` arm died on the first task of the
first condition with

    embedder 'voyage:voyage-4': RuntimeError: VoyageEmbedder needs VOYAGE_API_KEY

surfaced as `PrefetchError: recall prefetch failed with exit 1`, which stopped the whole run. Two
launches were spent before it was diagnosed, because the error is truncated in the run log.

These tests exist so that switching embedders, or adding a provider, fails HERE rather than forty
minutes into a grid.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.recall.adapter import RecallAdapter

CONFIG = json.loads((REPO / "adapters" / "recall" / "config.frozen.json").read_text("utf-8"))


@pytest.fixture
def adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RecallAdapter:
    # The location values are read from the environment by name, because this tree is public.
    for key in ("ssh_host", "remote_root", "remote_python", "remote_env_file", "dsn"):
        name = CONFIG.get(f"{key}_env")
        if name:
            monkeypatch.setenv(name, f"test-{key}")
    base_prompt = tmp_path / "base.md"
    base_prompt.write_text("static prompt", encoding="utf-8")
    return RecallAdapter(tmp_path / "staging", base_prompt)


def test_the_hosted_embedders_api_key_reaches_the_child(adapter, monkeypatch):
    """Without this the run dies at the first task, not at startup."""
    monkeypatch.setenv("VOYAGE_API_KEY", "sentinel-key")
    env = adapter.search_env("bench-test")
    assert env.get("VOYAGE_API_KEY") == "sentinel-key"


def test_an_absent_key_is_simply_absent_rather_than_empty(adapter, monkeypatch):
    """An empty string is not a missing key: it would be sent to the provider and rejected."""
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    env = adapter.search_env("bench-test")
    assert "VOYAGE_API_KEY" not in env


def test_the_frozen_embedder_has_its_credential_in_the_passthrough(adapter, monkeypatch):
    """Whatever provider the FROZEN config names, its key must be passed through.

    This is the test that would have caught the original defect, because it reads the provider out
    of `config.frozen.json` rather than hard-coding one. Change the embedder to a provider whose
    key is not passed through and this goes red.
    """
    embedder = str(CONFIG["embedder"])
    provider = embedder.split(":", 1)[0].upper()
    if provider in {"FASTEMBED", "STUB", "HASH"}:
        pytest.skip(f"{embedder} is local and needs no credential")
    key = f"{provider}_API_KEY"
    monkeypatch.setenv(key, "sentinel-key")
    env = adapter.search_env("bench-test")
    assert env.get(key) == "sentinel-key", (
        f"the frozen embedder is {embedder!r}, so {key} must reach the child environment; "
        f"_server_env replaces the environment rather than extending it"
    )


def test_the_environment_is_replaced_not_extended(adapter, monkeypatch):
    """The property that makes the passthrough list load-bearing in the first place."""
    monkeypatch.setenv("SOME_UNRELATED_VARIABLE", "leaked")
    env = adapter.search_env("bench-test")
    assert "SOME_UNRELATED_VARIABLE" not in env


def test_the_search_path_runs_under_the_frozen_environment(adapter):
    """`production` is the only switch that routes search through `GenerationStore`.

    Without it recall answers from the legacy path, reports `generation -` and
    `calibration status missing`, and a strict policy refuses. The frozen config declared
    `environment: production` all along; it reached the remote command and the MCP server env but
    not this one, so the published search path and the prefetch path disagreed about which store
    they read. That cost a launch.
    """
    env = adapter.search_env("bench-test")
    assert env.get("RECALL_ENV") == str(CONFIG["environment"])
    assert env["RECALL_ENV"] == "production", "the frozen config must keep serving from generations"
