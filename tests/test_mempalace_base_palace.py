"""A prebuilt base palace lets the shared haystack be mined once, not once per condition.

MemPalace ingest runs at ~30 documents/min (measured 2026-08-31 on the live run by counting
distinct `source_file` values in its Chroma store). The hard corpus is 4,889 documents per
condition of which 4,704 are the identical haystack, so mining all five from scratch is ~10.5
hours, nearly all of it re-embedding the same synthetic documents.

The reuse itself was verified on a 20-document probe BEFORE being relied on: a copied palace
retains its contents, accepts further mining, leaves the original untouched, retrieves newly mined
content, and returns identical top-3 results to a monolithically built palace across three queries.
These tests cover the wiring around that, which is where a silent corpus shortfall would come from.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.mempalace.adapter import MemPalaceAdapter

A = MemPalaceAdapter


def _palace(path: Path, sources: list[str]) -> Path:
    """A minimal stand-in for a palace: the store, and the rows the count reads."""
    path.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path / "chroma.sqlite3") as db:
        db.execute("create table embedding_metadata (id integer, key text, string_value text)")
        for i, src in enumerate(sources):
            db.execute("insert into embedding_metadata values (?, 'source_file', ?)", (i, src))
    return path


# --- the base is OFF unless asked for -----------------------------------------------------------


def test_no_base_by_default(monkeypatch):
    """The default must be unchanged behaviour: a run does not change shape by accident."""
    monkeypatch.delenv("MEMPALACE_BASE_PALACE", raising=False)
    assert A.base_palace() is None


def test_an_empty_value_is_no_base(monkeypatch):
    monkeypatch.setenv("MEMPALACE_BASE_PALACE", "   ")
    assert A.base_palace() is None


def test_a_path_that_is_not_a_palace_is_refused(monkeypatch, tmp_path):
    """Pointing at the wrong directory must fail loudly, not mine a full corpus in silence."""
    empty = tmp_path / "not-a-palace"
    empty.mkdir()
    monkeypatch.setenv("MEMPALACE_BASE_PALACE", str(empty))
    with pytest.raises(RuntimeError, match="not a MemPalace palace"):
        A.base_palace()


# --- the count is read from the STORE, not the input --------------------------------------------


def test_the_filed_count_is_read_from_the_store(tmp_path):
    """Counted from what the palace HOLDS, not from what was handed to it.

    Re-deriving from the input could not detect a base built from a different corpus, which is the
    single failure the shortfall guard exists to catch.
    """
    assert A.filed_document_count(_palace(tmp_path / "p", ["a", "b", "b", "c"])) == 3


def test_the_count_is_zero_for_an_empty_store(tmp_path):
    assert A.filed_document_count(_palace(tmp_path / "p", [])) == 0


# --- the shortfall guard ------------------------------------------------------------------------
# This is the mutation that survived the first version of these tests: the helpers were covered and
# the guard they feed was not.


def test_an_exactly_matching_base_is_accepted(tmp_path):
    A.check_base_covers_shared(tmp_path, 4704, 4704, "synthetic/")


def test_a_base_holding_FEWER_documents_is_refused(tmp_path):
    """The silent-thinner-corpus case: every condition would lose what the base lacks."""
    with pytest.raises(RuntimeError, match="holds 4000 document"):
        A.check_base_covers_shared(tmp_path, 4000, 4704, "synthetic/")


def test_a_base_holding_MORE_documents_is_also_refused(tmp_path):
    """Contamination, not shortfall: documents in no condition's corpus, retrievable in all five.

    `>=` would have let this through, which is why the check is exact equality.
    """
    with pytest.raises(RuntimeError, match="holds 5000 document"):
        A.check_base_covers_shared(tmp_path, 5000, 4704, "synthetic/")


def test_the_refusal_names_the_way_out(tmp_path):
    """A guard that stops a 10-hour job must say how to proceed."""
    with pytest.raises(RuntimeError, match="MEMPALACE_BASE_PALACE"):
        A.check_base_covers_shared(tmp_path, 1, 2, "synthetic/")


# --- the JOINs inside ingest ---------------------------------------------------------------------
# The helpers above can all be correct while `ingest` fails to use them. Both of these mutations
# survived the first version of this file, which is the same shape as the defect that voided
# official-002's first run: two correct halves and an untested join. Checked against the AST so
# reformatting cannot break them and deleting the code cannot pass them.


def _ingest_source() -> str:
    import ast

    tree = ast.parse((REPO / "adapters" / "mempalace" / "adapter.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "ingest":
            return ast.unparse(node)
    raise AssertionError("MemPalaceAdapter.ingest not found")


def test_ingest_copies_the_base_palace():
    """Without the copy the palace lacks the shared documents AND the feed skips them.

    The runtime guard catches this, because the count would not match, but a test that only
    exercises the guard would let the call itself be deleted.
    """
    source = _ingest_source()
    assert "copytree" in source, "ingest no longer copies the base palace"


def test_ingest_skips_the_shared_documents_when_a_base_is_used():
    """Not correctness (mine dedups anyway) but ~23 minutes per condition of pure skipping.

    A silently lost optimisation is worth a test precisely because nothing else would report it:
    the run would simply take three hours longer and still be right.
    """
    source = _ingest_source()
    assert "shared_prefix" in source and "continue" in source, (
        "ingest no longer skips the shared documents when a base palace is in use"
    )
