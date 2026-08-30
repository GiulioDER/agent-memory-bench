"""The per-arm retrieval hook: `MemoryAdapter.search`.

Until this existed, "product X retrieves better than product Y" was unmeasurable here. Every
arm's retrieval happens inside its own MCP server and the harness only ever saw tool calls in a
transcript, so `scripts/retrieval_probe.py` could characterise the CORPUS and nothing else.

Three properties carry the risk, and each has a test:

1. **Order is the payload.** `adapters/recall_prefetch.parse_prefetch_output` sorts its items by
   `memory_id`, which is harmless for a bundle injected whole and fatal for a ranked list: it
   would produce a hit@1 that is an artefact of identifier assignment. Anything on this path must
   preserve the order the product returned.
2. **Gating is declared truthfully and never invented.** `recall` has a trust threshold and can
   abstain; `fs_grep` has neither. An arm must refuse a gating it does not have rather than
   answer under a label that misdescribes it.
3. **An unimplemented arm raises rather than returning nothing.** An empty list is a legitimate
   answer meaning "found nothing", so an arm with no hook returning one would score as a product
   that retrieves badly.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters.fs_grep.adapter import FsGrepAdapter
from adapters.recall.adapter import RecallAdapter, parse_ranked_search
from harness.adapters.base import GATINGS, CorpusManifest, MemoryAdapter
from harness.tasks import discover_tasks

REPO = Path(__file__).resolve().parents[1]
BUNDLE = REPO / "corpus" / "claude_md_bundle_smoke.md"


def test_the_base_class_refuses_rather_than_returning_an_empty_list():
    """An arm with no hook must not be scoreable as a product that retrieves nothing."""

    class Unwired(MemoryAdapter):
        name = "unwired"

        def ingest(self, corpus, namespace):  # pragma: no cover - not exercised
            raise NotImplementedError

        def build(self, session_dir, namespace):  # pragma: no cover - not exercised
            raise NotImplementedError

        def admission_signal(self):  # pragma: no cover - not exercised
            raise NotImplementedError

    assert Unwired.supported_gatings == ()
    with pytest.raises(NotImplementedError, match="no ranked retrieval"):
        Unwired().search("ns", "query")


def test_recall_parsing_preserves_the_api_order():
    """Sorting by memory_id would make hit@1 an artefact of identifier assignment."""

    stdout = "chatter\n" + json.dumps(
        {
            "evidence": [
                {"memory_id": "zzz", "source_path": "sessions/ts-a/p01.jsonl", "score": 0.91},
                {"memory_id": "aaa", "source_path": "distractors/d001.jsonl", "score": 0.80},
                {"memory_id": "bbb", "source_path": "distractors/d002.jsonl", "score": 0.70},
            ]
        }
    )
    result = parse_ranked_search(stdout, gating="served", query="q", limit=10)
    assert [hit.source_path for hit in result.hits] == [
        "sessions/ts-a/p01.jsonl",
        "distractors/d001.jsonl",
        "distractors/d002.jsonl",
    ]
    assert [hit.rank for hit in result.hits] == [1, 2, 3]


def test_a_hit_with_no_source_is_dropped_and_counted():
    """It cannot be joined to a corpus document, and a placeholder would score against the wrong one.

    The counter is `unsourced`, not `unjoinable`, and the rename on 2026-08-30 was the point of
    the F-05 finding rather than cosmetic. This counts hits carrying NO source field at all.
    Whether a source that IS present joins the corpus manifest is a different question, it is
    the one recall actually failed (it returns rendered `.md` names), and it is answered by
    `ArmBackend.assert_joinable` against a real manifest. One name for both meant the second
    check looked as though it already existed.
    """

    stdout = json.dumps(
        {
            "evidence": [
                {"memory_id": "a", "score": 0.9},
                {"memory_id": "b", "source_path": "sessions/ts-a/p01.jsonl", "score": 0.8},
            ]
        }
    )
    result = parse_ranked_search(stdout, gating="served", query="q", limit=10)
    assert len(result.hits) == 1
    assert result.detail["unsourced"] == 1
    assert result.hits[0].rank == 1, "ranks must be contiguous after a drop"


def test_an_abstention_is_reported_rather_than_flattened_to_an_empty_list():
    """Declining is a decision; an empty list from an engaged product is a different outcome."""

    abstained = parse_ranked_search(
        json.dumps({"abstained": True, "evidence": []}), gating="served", query="q", limit=5
    )
    assert abstained.abstained is True and abstained.hits == ()

    empty = parse_ranked_search(
        json.dumps({"evidence": []}), gating="served", query="q", limit=5
    )
    assert empty.abstained is False and empty.hits == ()


def test_recall_refuses_a_raw_list_because_it_would_move_the_frozen_config():
    adapter = RecallAdapter(staging_root=tempfile.mkdtemp(), base_prompt_file=BUNDLE)
    assert adapter.supported_gatings == ("served",)
    with pytest.raises(ValueError, match="no session runs"):
        adapter.search("ns", "q", gating="raw")


def test_recall_search_does_not_shell_out_when_a_runner_is_injected(monkeypatch):
    """The command shape is part of the contract: -k must carry the limit, not prefetch_k.

    A DSN is set because `search_env` refuses to guess a database, which is the right guard and
    fires before the injected runner is ever reached. It points at nothing: no connection is
    opened here, since the runner never runs the command.
    """

    monkeypatch.setenv("RECALL_DSN", "postgresql://unused/probe-contract-test")
    seen = {}

    def fake_runner(command, **kwargs):
        seen["command"] = command
        seen["env"] = kwargs.get("env")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {"evidence": [{"source_path": "sessions/ts-a/p01.jsonl", "score": 1.0}]}
            ),
            stderr="",
        )

    adapter = RecallAdapter(staging_root=tempfile.mkdtemp(), base_prompt_file=BUNDLE)
    result = adapter.search("tenant-x", "question", limit=7, runner=fake_runner)
    assert result.gating == "served"
    assert result.hits[0].source_path == "sessions/ts-a/p01.jsonl"
    assert "--tenant" in seen["command"] and "tenant-x" in seen["command"]
    assert seen["command"][seen["command"].index("-k") + 1] == "7"
    assert seen["env"]["RECALL_TENANT"] == "tenant-x"


def test_fs_grep_supports_raw_only_and_says_why():
    adapter = FsGrepAdapter(staging_root=tempfile.mkdtemp(), base_prompt_file=BUNDLE)
    assert adapter.supported_gatings == ("raw",)
    with pytest.raises(ValueError, match="no trust policy"):
        adapter.search("ns", "q", gating="served")


def test_fs_grep_hits_join_back_to_corpus_documents():
    """A hit nobody can join to a corpus path cannot be scored, so the flattening must reverse."""

    adapter = FsGrepAdapter(staging_root=tempfile.mkdtemp(), base_prompt_file=BUNDLE)
    corpus = CorpusManifest.load(REPO / "corpus")
    adapter.ingest(corpus, "ns")
    task = next(t for t in discover_tasks() if t.task_id == "ts-crlf-export")
    result = adapter.search("ns", task.prompt, gating="raw", limit=10)

    assert result.hits, "the arm retrieved nothing at all from a 195-document corpus"
    for hit in result.hits:
        assert hit.source_path in corpus.sessions, (
            f"{hit.source_path} is not a document in the corpus manifest; the rendered-name "
            f"flattening no longer reverses and every arm number would be unscoreable"
        )
    assert [hit.rank for hit in result.hits] == list(range(1, len(result.hits) + 1))


def test_fs_grep_refuses_to_search_a_store_it_has_not_ingested():
    adapter = FsGrepAdapter(staging_root=tempfile.mkdtemp(), base_prompt_file=BUNDLE)
    with pytest.raises(FileNotFoundError, match="ingest before searching"):
        adapter.search("never-ingested", "q", gating="raw")


def test_every_declared_gating_is_a_known_one():
    for adapter_cls in (FsGrepAdapter, RecallAdapter):
        for gating in adapter_cls.supported_gatings:
            assert gating in GATINGS
