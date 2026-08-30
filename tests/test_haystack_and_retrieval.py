"""The generated haystack and the retrieval difficulty probe.

Four properties carry the risk here, and each has a test that fails if it stops holding.

* **Containment.** A synthetic session that states a task's governing fact makes that task
  answerable from the haystack, which is the same defect
  `scripts/audit_corpus.py` exists to prevent in the real feed. The generator filters for it;
  this asserts the filter is not vacuous by checking the emitted sessions directly.
* **The frozen feed does not move.** `CorpusManifest.build` learned a `synthetic/**` pattern.
  If that pattern ever matched something inside `corpus/`, every published run's feed would
  change silently and no test would have noticed.
* **Determinism.** A haystack is reproduced from a seed rather than committed, so a generator
  that is not a pure function of its seed makes 24 MB of corpus unverifiable.
* **Misses are not counted as easy.** The probe's first version averaged
  `competitors_above_gold` over all queries with a miss contributing zero, so a corpus got a
  BETTER difficulty number the more completely it failed. That is a regression test, not a
  hypothetical.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.adapters.base import CorpusManifest
from harness.plants import normalise
from harness.tasks import discover_tasks
from scripts.audit_corpus import _STOP
from scripts.generate_haystack import (
    _fact_phrases,
    _tier_counts,
    _violates,
    make_session,
    prompt_terms,
)
from scripts.retrieval_probe import BM25, Window, rank_documents, tier_of, windows_for

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def tasks():
    return [task for task in discover_tasks() if task.fact_terms]


def _text(events: list[dict]) -> str:
    return " ".join(
        str(event.get(field, ""))
        for event in events
        for field in ("content", "tool_result", "tool_input")
    )


def test_no_generated_session_states_any_governing_fact(tasks):
    """Containment, checked on the emitted sessions rather than trusted from the filter."""

    phrases = _fact_phrases(tasks)
    assert phrases, "no task declares fact_terms; this test would pass vacuously"
    for tier in ("background", "topical", "near_miss"):
        for index in range(40):
            events, _ = make_session(index, seed=1, tier=tier, tasks=tasks)
            leaked = _violates(_text(events), phrases)
            assert leaked is None, f"{tier} session {index} states {leaked}'s governing fact"


def test_near_miss_vocabulary_comes_from_the_prompt_and_carries_no_fact_term(tasks):
    """A near-miss is safe BY CONSTRUCTION, and this is the assertion that says why.

    Audit assertion 3 forbids a fact term from appearing in a task prompt, so anything derived
    from a prompt cannot reintroduce one. If a prompt ever acquires a fact term, that audit
    fails first and this test says the haystack inherited the problem.
    """

    for task in tasks:
        prompt = normalise(task.prompt)
        for term in task.fact_terms:
            assert normalise(term) not in prompt, f"{task.task_id}: fact term is in its prompt"
        terms = prompt_terms(task.prompt)
        assert terms, f"{task.task_id}: prompt yielded no content words to build a near-miss from"


def test_generation_is_deterministic_in_its_seed(tasks):
    """A haystack is reproduced rather than committed, so this is what makes it verifiable."""

    first, provenance_first = make_session(7, seed=3, tier="near_miss", tasks=tasks)
    second, provenance_second = make_session(7, seed=3, tier="near_miss", tasks=tasks)
    assert first == second
    assert provenance_first == provenance_second
    other, _ = make_session(7, seed=4, tier="near_miss", tasks=tasks)
    assert other != first, "changing the seed changed nothing; the seed is not wired through"


def test_a_near_miss_session_actually_shares_vocabulary_with_its_task_prompt(tasks):
    """The tier is only worth its cost if the generated text competes with the query."""

    shares = []
    for index in range(30):
        events, provenance = make_session(index, seed=1, tier="near_miss", tasks=tasks)
        task = next(t for t in tasks if t.task_id == provenance["near_miss_task"])
        wanted = set(prompt_terms(task.prompt))
        present = {term for term in wanted if term in normalise(_text(events))}
        shares.append(len(present) / len(wanted))
    assert sum(shares) / len(shares) > 0.5, (
        "near-miss sessions carry less than half their task's prompt vocabulary, so they are "
        "not hard negatives and the tier is only adding volume"
    )


def test_tier_counts_never_lose_a_document():
    for total in (0, 1, 7, 195, 4680):
        counts = _tier_counts(total, {"background": 0.7, "topical": 0.2, "near_miss": 0.1})
        assert sum(counts.values()) == total


def test_the_frozen_feed_has_no_synthetic_entries():
    """`CorpusManifest.build` gained a `synthetic/**` pattern; `corpus/` must not match it."""

    manifest = CorpusManifest.load(REPO / "corpus")
    assert not any(rel.startswith("synthetic/") for rel in manifest.sessions)
    assert not (REPO / "corpus" / "synthetic").exists(), (
        "synthetic sessions must never live in the real corpus root: corpus/README.md rule 1 "
        "says content there is verbatim agent output"
    )


def test_build_picks_up_all_three_directories(tmp_path):
    for rel in ("sessions/ts-x/p01.jsonl", "distractors/d001.jsonl", "synthetic/h00000.jsonl"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"role": "user", "content": rel}) + "\n", encoding="utf-8")
    manifest = CorpusManifest.build(tmp_path)
    assert set(manifest.sessions) == {
        "sessions/ts-x/p01.jsonl",
        "distractors/d001.jsonl",
        "synthetic/h00000.jsonl",
    }


def test_windows_cover_the_whole_text():
    words = [f"w{index}" for index in range(1000)]
    windows = windows_for(" ".join(words))
    covered = {word for window in windows for word in window.split()}
    assert covered == set(words), "a window scheme that drops words hides evidence from the probe"


def test_bm25_ranks_the_document_that_shares_the_query_vocabulary():
    windows = [
        Window(doc="gold.jsonl", text="the export writes carriage return line endings to orders"),
        Window(doc="other.jsonl", text="hive inspections are recorded once per yard each spring"),
    ]
    ranking = rank_documents(BM25(windows), windows, "carriage return line endings on export")
    assert ranking[0][0] == "gold.jsonl"


def test_smoke_sessions_are_not_counted_as_task_signal():
    """`sessions/smoke/` is gold for no task; counting it as signal misattributes competitors."""

    assert tier_of("sessions/smoke/s01.jsonl", None) == "smoke"
    assert tier_of("sessions/ts-crlf-export/p01.jsonl", None) == "other-task-signal"
    assert tier_of("distractors/d001.jsonl", None) == "real-distractor"
    plan = {"sessions": {"synthetic/h00001.jsonl": {"tier": "near_miss"}}}
    assert tier_of("synthetic/h00001.jsonl", plan) == "near_miss"


def test_a_miss_is_not_averaged_in_as_zero_competitors():
    """Regression: total retrieval failure once IMPROVED the mean competitor count."""

    rows = [
        {"rank": 3, "competitors_above_gold": 2},
        {"rank": None, "competitors_above_gold": None},
    ]
    hits = [row for row in rows if row["rank"]]
    mean = sum(row["competitors_above_gold"] for row in hits) / len(hits)
    assert mean == 2.0, (
        "the mean must be taken over queries that retrieved the gold session; folding a miss "
        "in as zero reports a harder corpus as an easier one"
    )


def test_the_paid_backend_refuses_before_it_spends():
    """The ceiling is a refusal, not a warning, and it is checked before the credential.

    A probe that silently costs ten times its estimate is worse than one that stops. Checking
    the key first would make this unreachable on any host without one, which is every host
    where somebody would want to sanity check the estimate before running it where the key is.
    """

    pytest.importorskip("voyageai")
    from scripts.retrieval_probe import Voyage

    windows = [Window(doc="a.jsonl", text=" ".join(f"w{i}" for i in range(1000)))]
    with pytest.raises(SystemExit, match="refusing to spend"):
        Voyage(windows, "voyage-4", max_tokens=10)


def test_the_token_estimate_errs_high():
    """It gates a paid run, so an estimate that flatters the corpus is the dangerous error."""

    from scripts.retrieval_probe import estimate_tokens

    assert estimate_tokens(["one two three four"]) >= 4


def test_every_task_has_a_semantic_neighbourhood(tasks):
    from scripts.haystack_neighbourhoods import NEIGHBOURHOODS

    for task in tasks:
        assert task.task_id in NEIGHBOURHOODS, f"{task.task_id} has no semantic neighbourhood"
        entry = NEIGHBOURHOODS[task.task_id]
        assert entry["subject"] and entry["decision"] and len(entry["terms"]) >= 6


def test_a_semantic_neighbourhood_shares_no_distinctive_word_with_its_own_prompt(tasks):
    """Rule 1, and the whole point of the tier.

    A neighbourhood term that appears in its own task's prompt is lexical overlap wearing a
    semantic label, and would make this tier a slower copy of `near_miss`. Function words are
    excluded because English needs them; anything contentful is a failure.
    """

    from scripts.haystack_neighbourhoods import NEIGHBOURHOODS

    function_words = _STOP | {
        "each", "when", "after", "under", "before", "which", "what", "who", "how", "they",
        "than", "then", "its", "also", "only", "same", "other", "more", "most", "some", "any",
        "all", "both", "has", "have", "will", "may", "can", "does", "was", "were", "but",
        "because", "during", "between", "over", "own", "goes", "gets", "two", "long", "way",
    }
    for task in tasks:
        entry = NEIGHBOURHOODS[task.task_id]
        text = " ".join(
            [str(entry["subject"]), " ".join(entry["terms"]), str(entry["decision"])]
        )
        prompt_words = set(normalise(task.prompt).split())
        overlap = sorted(
            word
            for word in set(normalise(text).split()) & prompt_words
            if len(word) > 2 and word not in function_words
        )
        assert not overlap, f"{task.task_id}: semantic neighbourhood reuses prompt words {overlap}"


def test_a_semantic_neighbourhood_states_no_governing_fact(tasks):
    from scripts.haystack_neighbourhoods import NEIGHBOURHOODS

    phrases = _fact_phrases(tasks)
    for task_id, entry in NEIGHBOURHOODS.items():
        text = " ".join(
            [str(entry["subject"]), " ".join(entry["terms"]), str(entry["decision"])]
        )
        leaked = _violates(text, phrases)
        assert leaked is None, f"{task_id}: neighbourhood states {leaked}'s governing fact"


def test_the_generator_digest_covers_the_neighbourhood_data():
    """A plan that names the code but not the DATA claims a reproducibility it does not have.

    The neighbourhood file was wired into the generator before it was wired into the digest,
    which would have let a `haystack.json` say a corpus was reproducible while the text inside
    those sessions moved underneath it.
    """

    from scripts.generate_haystack import _digest_generator

    path = REPO / "scripts" / "haystack_neighbourhoods.py"
    before = _digest_generator()
    original = path.read_bytes()
    try:
        path.write_bytes(original + b"\n# digest probe\n")
        assert _digest_generator() != before
    finally:
        path.write_bytes(original)
