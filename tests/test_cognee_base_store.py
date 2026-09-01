"""A prebuilt base store lets the shared haystack be extracted once, not once per condition.

cognee needs this more than MemPalace did, and MemPalace needed it enough to be deferred out of
`official-002` over it. There the repeated cost was local embedding, paid in hours; here every
repeat is an LLM extraction pass over the same synthetic documents, paid in hours AND tokens.
Measured 2026-09-01 in Docker: 1,616 tokens and two LLM calls per document, so a 4,704-document
shared haystack is roughly 7.6M tokens and 9,400 calls per condition, five times over, for an
identical result each time.

⛔ **The reuse itself is NOT verified.** MemPalace's equivalent was proven on a 20-document probe
before being relied on: a copied store retains its contents, accepts further ingest, leaves the
original untouched, and returns the same top results as a monolithic build. That probe cannot run
on this workstation, whose CPU has no AVX and therefore cannot execute cognee's vector store, so it
ships as `scripts/cognee_base_store_probe.py`. These tests cover the WIRING around the reuse, which
is where a silent corpus shortfall would come from; they are not evidence that the reuse is sound.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import json

from adapters.cognee.adapter import CogneeAdapter

CONFIG = json.loads(
    (REPO / "adapters" / "cognee" / "config.frozen.json").read_text(encoding="utf-8")
)
BASE_ENV = str(CONFIG["base_store_env"])


def _store(path: Path, names: list[str]) -> Path:
    """A minimal stand-in for a cognee store: the relational database and the rows counted."""

    database = CogneeAdapter.relational_db(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as db:
        db.execute("create table data (id integer, name text, raw_data_location text)")
        for index, name in enumerate(names):
            db.execute(
                "insert into data values (?, ?, ?)", (index, name, f"/feed/{name}.md")
            )
    return path


@pytest.fixture()
def adapter(tmp_path, monkeypatch):
    prompt = tmp_path / "claude_md.md"
    prompt.write_text("# Fixture\n", encoding="utf-8")
    venv = tmp_path / "v"
    (venv / "Scripts").mkdir(parents=True)
    for stem in ("python.exe", "cognee-mcp.exe"):
        (venv / "Scripts" / stem).write_bytes(b"")
    monkeypatch.setenv(CONFIG["venv_env"], str(venv))
    monkeypatch.setenv(CONFIG["store_root_env"], str(tmp_path / "s"))
    monkeypatch.setenv(CONFIG["llm"]["api_key_env"], "test-key-not-a-real-one")
    return CogneeAdapter(tmp_path / "staging", prompt)


# --- the base is OFF unless asked for -----------------------------------------------------------


def test_no_base_by_default(adapter, monkeypatch):
    """The default must be unchanged behaviour: a run does not change shape by accident."""

    monkeypatch.delenv(BASE_ENV, raising=False)
    assert adapter.base_store() is None


def test_an_empty_value_is_no_base(adapter, monkeypatch):
    monkeypatch.setenv(BASE_ENV, "   ")
    assert adapter.base_store() is None


def test_a_path_that_is_not_a_store_is_refused(adapter, monkeypatch, tmp_path):
    """Pointing at the wrong directory must fail loudly, not extract a full corpus in silence."""

    empty = tmp_path / "not-a-store"
    empty.mkdir()
    monkeypatch.setenv(BASE_ENV, str(empty))
    with pytest.raises(RuntimeError, match="not a cognee store"):
        adapter.base_store()


def test_a_real_store_is_accepted(adapter, monkeypatch, tmp_path):
    base = _store(tmp_path / "base", ["synthetic__a", "synthetic__b"])
    monkeypatch.setenv(BASE_ENV, str(base))
    assert adapter.base_store() == base


# --- the count comes from the STORE, not from the manifest --------------------------------------


def test_the_count_reads_what_the_store_holds(tmp_path):
    """Counting the input would re-derive the manifest and could not detect a wrong base."""

    base = _store(tmp_path / "base", ["synthetic__a", "synthetic__b", "synthetic__c"])
    assert CogneeAdapter.filed_document_count(base) == 3


def test_the_count_is_distinct_by_name(tmp_path):
    """The same document ingested from a base feed and a condition feed has two paths, one name."""

    base = _store(tmp_path / "base", ["synthetic__a", "synthetic__a", "synthetic__b"])
    assert CogneeAdapter.filed_document_count(base) == 2


# --- coverage is EXACT, in both directions ------------------------------------------------------


def test_a_thinner_base_is_refused(tmp_path):
    """⛔ The failure this guard exists for: every condition would lose the missing documents,
    the arm would be measured on a corpus nobody described, and nothing downstream could tell."""

    with pytest.raises(RuntimeError, match="holds 3 document"):
        CogneeAdapter.check_base_covers_shared(tmp_path, 3, 4704, "synthetic/")


def test_a_FATTER_base_is_refused_too(tmp_path):
    """Extra documents are in no condition's corpus yet retrievable in all of them, which is
    contamination rather than a shortfall and is harder to see."""

    with pytest.raises(RuntimeError, match="holds 4705 document"):
        CogneeAdapter.check_base_covers_shared(tmp_path, 4705, 4704, "synthetic/")


def test_an_exact_base_passes(tmp_path):
    CogneeAdapter.check_base_covers_shared(tmp_path, 4704, 4704, "synthetic/")


# --- the dataset name is what makes reuse possible at all ---------------------------------------


def test_one_dataset_name_across_namespaces(adapter):
    """A per-namespace name would put the copied documents in a dataset the condition never
    queries: the arm would retrieve nothing with every guard green."""

    assert adapter.dataset("bench-absent") == adapter.dataset("bench-superseded")


def test_the_probe_that_would_verify_the_reuse_exists_and_says_it_is_unrun():
    """The wiring above is not evidence. MemPalace's reuse was proven on a 20-document probe
    BEFORE being relied on, and this arm's equivalent cannot run on this host's CPU."""

    probe = REPO / "scripts" / "cognee_base_store_probe.py"
    assert probe.is_file(), "the reuse ships without the probe that would justify it"
    text = probe.read_text(encoding="utf-8")
    for claim in ("retains", "identical", "untouched"):
        assert claim in text, f"the probe does not check that a copied store {claim}"
