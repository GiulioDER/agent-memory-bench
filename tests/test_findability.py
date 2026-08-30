"""A plant nothing retrieves cannot mislead anybody, and nothing else here checks for that.

Every other gate checks a plant is CORRECT. `audit_plants` checks it leaks no true fact;
`test_damage_detection` checks its signature fires on the plant and not on a factless session.
A plant can pass all of them and still be inert.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pytest

from harness.retrieval import Bm25Index, tokenize
from scripts.audit_findability import CANDIDATE_DEPTH, WINDOW, rank_plants


def test_a_rarer_term_outranks_a_common_one():
    """The property a plain overlap score lacks, and the reason this is BM25.

    Two proxies were tried first and both failed: absolute overlap could not separate a plant
    ranked 4th from one ranked 45th, and ranking by that overlap put a plant truly 61st at 13th.
    Findability is relative, and inverse document frequency is what makes it so.
    """

    common = "the pipeline runs nightly"
    documents = {f"d{i}": common for i in range(20)}
    documents["rare"] = common + " palindromic aardvark"
    index = Bm25Index(documents)

    ranking = index.ranking("palindromic aardvark")
    assert ranking[0][0] == "rare"
    assert ranking[0][1] > 0
    assert ranking[1][1] == 0, "a document without the rare terms must score nothing for them"


def test_a_longer_document_is_not_rewarded_for_padding():
    """Length normalisation. Without it, the fix for an inert plant would be to make it longer."""

    index = Bm25Index({"short": "atomic rename", "padded": "atomic rename " + "filler " * 400})
    assert index.score("atomic rename", "short") > index.score("atomic rename", "padded")


def test_tokenize_drops_stopwords_and_single_characters():
    assert "the" not in tokenize("the atomic rename")
    assert "a" not in tokenize("a b atomic")
    assert "atomic" in tokenize("the atomic rename")


def test_ranking_is_reproducible_under_ties():
    """A rank that moves between runs cannot support any decision at all."""

    documents = {name: "identical text here" for name in ("c", "a", "b")}
    index = Bm25Index(documents)
    first = [name for name, _ in index.ranking("identical")]
    assert first == sorted(first), "ties must break by name"
    assert first == [name for name, _ in index.ranking("identical")]


def test_every_planted_session_is_reachable_at_all():
    """Mutation: stage a plant whose recording never lands in the corpus.

    Not a rank threshold. This is the weaker, unambiguous half: a plant that is not PRESENT in
    its own condition corpus is broken however you rank it, and no proxy disagreement can excuse
    it. Skipped when the corpus has not been assembled in this checkout.
    """

    rows = rank_plants("adjacent")
    if not rows:
        pytest.skip("corpus/conditions/adjacent/seed-1 is not assembled here")
    missing = [task for task, rank, _n in rows if rank is None]
    assert not missing, f"planted session absent from its own condition corpus: {missing}"


def test_the_audit_reports_rather_than_gates():
    """Mutation: turn the candidate list into a failure.

    Two independent BM25 implementations disagreed by up to 51 rank positions on exactly this
    depth range, and neither is ground truth because the products retrieve with embeddings. A
    hard threshold on a number that unstable would fail builds arbitrarily, so this stays a
    report and a human decides.
    """

    source = (REPO / "scripts" / "audit_findability.py").read_text(encoding="utf-8")
    assert "return 0" in source
    assert "raise SystemExit(1)" not in source, (
        "audit_findability must not fail a build on a rank two implementations cannot agree on"
    )
    assert CANDIDATE_DEPTH > 0 and WINDOW > 0
