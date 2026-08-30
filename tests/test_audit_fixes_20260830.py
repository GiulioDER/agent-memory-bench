"""Regression tests for the CCA audit of 2026-08-30. One test per confirmed finding.

Each test below FAILED against the code as it stood before its fix. That is the point: a
regression test written after a fix, which would also have passed before it, proves nothing, and
several of the defects these pin were invisible precisely because the tests that existed asserted
the assumption under dispute rather than the behaviour.

The finding IDs are from `.claude/audits/CONSOLIDATED.json`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from adapters.fs_grep.adapter import FsGrepAdapter
from adapters.recall.adapter import manifest_key, parse_ranked_search
from harness.abstention import Cell, usefulness
from harness.adapters.base import CorpusManifest, RankedHit, RankedResult
from harness.damage import CORPUS_CONDITIONS, PRESENT, Outcome
from scripts.retrieval_probe import ArmBackend, estimate_tokens, load_windows
from scripts.task_admission import verdict
from scripts.verify_run import _condition_of, verify

REPO = Path(__file__).resolve().parents[1]
BUNDLE = REPO / "corpus" / "claude_md_bundle_smoke.md"


def _present_cells(n_arms: int, n_tasks: int, *, abstaining: str = "armA") -> list[Cell]:
    arms = ["armA"] + [f"other{i}" for i in range(n_arms - 1)]
    return [
        Cell(
            task_id=f"ts-{task}",
            seed=0,
            arm=arm,
            condition=PRESENT,
            outcome=Outcome.NEUTRAL_FAILURE,
            abstained=(arm == abstaining),
        )
        for task in range(n_tasks)
        for arm in arms
    ]


# --------------------------------------------------------------------------------------------
# F-01 (Critical): missed_rate divided an arm-filtered numerator by an all-arms denominator.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("n_arms", [2, 3, 5])
def test_f01_missed_rate_does_not_depend_on_how_many_other_arms_ran(n_arms):
    """The published rate was the truth divided by the arm count.

    Before the fix this returned 0.5 / 0.3333 / 0.2 for n_arms 2 / 3 / 5, so adding an unrelated
    vendor to a grid silently changed every other vendor's number. The five-arm case is the shape
    `official-001` actually ran.
    """

    result = usefulness(_present_cells(n_arms, 4), "armA")
    assert result["missed_rate"] == 1.0
    assert result["missed_n_cells"] == result["missed_n_present_cells"] == 4


def test_f01_the_denominator_is_published_so_the_rate_is_recomputable():
    """`missed_n_cells` and `missed_rate` disagreed in one dict with no way to reconcile them."""

    result = usefulness(_present_cells(3, 6), "armA")
    assert result["missed_n_cells"] / result["missed_n_present_cells"] == result["missed_rate"]


# --------------------------------------------------------------------------------------------
# F-02 / F-03: a hardcoded provenance claim, and a power flag counting the wrong unit.
# --------------------------------------------------------------------------------------------


def test_f02_never_run_is_derived_rather_than_asserted():
    """It was the literal `True`, so the first real run would publish numbers calling itself unrun."""

    assert usefulness([], "armA")["never_run"] is True
    assert usefulness(_present_cells(2, 3), "armA")["never_run"] is False


def test_f03_underpowered_counts_tasks_not_cells():
    """Seeds of one task share a prompt, a fixture and a memo; this module says so itself."""

    cells = []
    for task in range(3):
        for seed in range(4):
            cells.append(
                Cell(f"ts-{task}", seed, "bare", PRESENT, Outcome.NEUTRAL_FAILURE)
            )
            cells.append(Cell(f"ts-{task}", seed, "armA", PRESENT, Outcome.SOLVED))
    result = usefulness(cells, "armA")
    assert result["sensitivity_n_cells"] == 12
    assert result["sensitivity_n_tasks"] == 3
    assert result["underpowered"] is True, "12 cells over 3 clustered tasks is not 12 observations"


# --------------------------------------------------------------------------------------------
# F-04: the spend estimator counted WORDS and its docstring claimed it erred high. It erred low.
# --------------------------------------------------------------------------------------------


def test_f04_estimator_exceeds_the_real_token_count_on_this_repositorys_own_corpus():
    """The corpus-level property the ceiling actually operates on.

    The old word-based estimator returned 247,480 against 315,734 real cl100k_base tokens, a
    ratio of 0.784, so a run approved at exactly `--max-tokens` billed about 1.27x that.
    """

    tiktoken = pytest.importorskip("tiktoken")
    encoder = tiktoken.get_encoding("cl100k_base")
    texts = [window.text for window in load_windows(REPO / "corpus")]
    real = sum(len(encoder.encode(text)) for text in texts)
    assert estimate_tokens(texts) >= real, (
        "the pre-flight estimate is below the real token count for the whole corpus, which is "
        "the granularity the --max-tokens ceiling is applied at"
    )


def test_f04_a_long_unbroken_run_is_not_estimated_as_one_token():
    """The word-based estimator returned 1 for a 4,000-character string with no spaces."""

    assert estimate_tokens(["a" * 4000]) > 500


# --------------------------------------------------------------------------------------------
# F-32: the ceiling refusal must not require the 41-second voyageai import.
# --------------------------------------------------------------------------------------------


def test_f32_the_spend_refusal_does_not_import_the_vendor_client():
    """Measured at 41.58s before the fix, 8.5% of the whole suite, to test word-count arithmetic.

    Run in a subprocess so the assertion is about what gets IMPORTED, which an in-process test
    cannot see once another test has already pulled voyageai in.
    """

    code = (
        f"import sys; sys.path.insert(0, {str(REPO)!r})\n"
        "from scripts.retrieval_probe import Voyage, Window\n"
        "try:\n"
        "    Voyage([Window(doc='a', text='x'*100000)], 'voyage-4', max_tokens=10)\n"
        "except SystemExit:\n"
        "    pass\n"
        "print('voyageai' in sys.modules)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=False
    )
    assert out.stdout.strip().endswith("False"), (
        f"the refusal imported voyageai; stdout={out.stdout!r} stderr={out.stderr[-400:]!r}"
    )


# --------------------------------------------------------------------------------------------
# F-07 / F-08: the recall parser conflated a parse failure with a zero-hit answer, and returned
# chunk-level hits that the probe scored as document ranks.
# --------------------------------------------------------------------------------------------


def test_f07_a_parse_failure_raises_rather_than_reading_as_found_nothing():
    """recall's own `_print_evidence` emits `json.dumps(payload, indent=2)`, i.e. multi-line.

    The reverse line scan matched nothing against real output, so every query came back empty and
    the arm published hit@1 0.000 as a fact about the vendor. The base class forbids exactly this
    conflation in the docstring of the method being implemented.
    """

    pretty = json.dumps({"evidence": [{"source_path": "sessions/ts-x/p01.jsonl"}]}, indent=2)
    parsed = parse_ranked_search(pretty, gating="served", query="q", limit=10)
    assert len(parsed.hits) == 1, "multi-line JSON must parse; recall pretty-prints"

    with pytest.raises(RuntimeError, match="no JSON"):
        parse_ranked_search("not json at all", gating="served", query="q", limit=10)

    empty = parse_ranked_search('{"evidence": []}', gating="served", query="q", limit=10)
    assert empty.hits == () and empty.detail["payload_found"] is True


def test_f08_chunks_of_one_document_collapse_to_one_ranked_hit():
    """Two chunks of one gold shard satisfied len(positions) == len(gold) and faked all_shards."""

    payload = json.dumps(
        {
            "evidence": [
                {"source_path": "sessions/xs-a/p01.jsonl", "score": 0.9},
                {"source_path": "sessions/xs-a/p01.jsonl", "score": 0.8},
                {"source_path": "sessions/xs-a/p02.jsonl", "score": 0.7},
            ]
        }
    )
    parsed = parse_ranked_search(payload, gating="served", query="q", limit=10)
    assert [hit.source_path for hit in parsed.hits] == [
        "sessions/xs-a/p01.jsonl",
        "sessions/xs-a/p02.jsonl",
    ]
    assert [hit.rank for hit in parsed.hits] == [1, 2]
    assert parsed.detail["chunks_returned"] == 3


# --------------------------------------------------------------------------------------------
# F-15: --namespace flowed unvalidated into a path that gets shutil.rmtree'd.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad", ["../../../../victim", "..", "a/../../b", "-rf", "", "with space", "x\\y"]
)
def test_f15_a_namespace_cannot_escape_its_staging_root(bad):
    """`_staging_dir('../../../../victim')` resolved outside the temp root, onto an rmtree."""

    adapter = FsGrepAdapter(staging_root=tempfile.mkdtemp(), base_prompt_file=BUNDLE)
    with pytest.raises(ValueError, match="namespace"):
        adapter.search(bad, "q", gating="raw")


def test_f15_an_ordinary_namespace_still_works():
    adapter = FsGrepAdapter(staging_root=tempfile.mkdtemp(), base_prompt_file=BUNDLE)
    adapter.ingest(CorpusManifest.load(REPO / "corpus"), "probe-1_ok")
    assert adapter.search("probe-1_ok", "carriage return line endings", gating="raw").hits


# --------------------------------------------------------------------------------------------
# F-06: recall's source_path is a RENDERED name and can never equal a manifest key.
# --------------------------------------------------------------------------------------------


def test_f06_every_real_manifest_key_round_trips_through_the_renderers_naming():
    """The property, over the actual corpus rather than an example.

    `render_corpus` flattens `sessions/ts-x/p01.jsonl` to `sessions__ts-x__p01.md`, so a hit came
    back under a name that joined nothing and the arm scored a structural zero.
    """

    manifest = CorpusManifest.load(REPO / "corpus")
    assert manifest.sessions, "the corpus manifest is empty; this test would prove nothing"
    for rel in manifest.sessions:
        rendered = rel[: -len(".jsonl")].replace("/", "__") + ".md"
        assert manifest_key(rendered) == rel
        assert manifest_key(f"/tmp/stage/feed/{rendered}") == rel


def test_f06_a_name_carrying_no_directory_information_is_left_visibly_unjoinable():
    """Inventing a `sessions/` prefix would manufacture a join that could be wrong."""

    assert manifest_key("plain.md") == "plain.md"
    assert manifest_key("already/a/key.jsonl") == "already/a/key.jsonl"


def test_f06_normalisation_happens_before_dedup():
    payload = json.dumps(
        {
            "evidence": [
                {"source_path": "/stage/feed/sessions__xs-a__p01.md", "score": 0.9},
                {"source_path": "sessions__xs-a__p01.md", "score": 0.8},
            ]
        }
    )
    parsed = parse_ranked_search(payload, gating="served", query="q", limit=10)
    assert [h.source_path for h in parsed.hits] == ["sessions/xs-a/p01.jsonl"]


# --------------------------------------------------------------------------------------------
# F-05: an arm whose identifiers do not join must refuse, not publish hit@1 0.000.
# --------------------------------------------------------------------------------------------


class _StubAdapter:
    name = "stub"
    supported_gatings = ("raw",)

    def __init__(self, sources):
        self._sources = sources

    def search(self, namespace, query, *, gating, limit=10):
        return RankedResult(
            hits=tuple(
                RankedHit(source_path=s, score=1.0 - i / 100, rank=i + 1)
                for i, s in enumerate(self._sources)
            ),
            gating=gating,
            abstained=False,
            query_sha256="0" * 64,
            detail={},
        )


def test_f05_a_total_join_failure_refuses_instead_of_scoring_zero():
    """0.000 from a broken join and 0.000 from a bad product are the same number."""

    arm = ArmBackend(_StubAdapter(["wrong__name.md", "other.txt"]), "ns", "raw", 10)
    arm.bind_corpus({"sessions/ts-x/p01.jsonl"})
    arm.ranking("anything")
    with pytest.raises(SystemExit, match="NONE join the corpus"):
        arm.assert_joinable()


def test_f05_a_partial_join_is_reported_rather_than_refused():
    """A partial failure is still a measurement; silence about it is the defect."""

    arm = ArmBackend(_StubAdapter(["sessions/ts-x/p01.jsonl", "junk.txt"]), "ns", "raw", 10)
    arm.bind_corpus({"sessions/ts-x/p01.jsonl"})
    arm.ranking("anything")
    arm.assert_joinable()
    assert (arm.hits_returned, arm.hits_joined) == (2, 1)
    assert arm.unjoinable_examples == ["junk.txt"]


def test_f05_an_arm_that_returned_nothing_is_not_a_join_failure():
    arm = ArmBackend(_StubAdapter([]), "ns", "raw", 10)
    arm.bind_corpus({"sessions/ts-x/p01.jsonl"})
    arm.ranking("anything")
    arm.assert_joinable()


# --------------------------------------------------------------------------------------------
# F-21 / F-22 / F-23: three copies of a four-condition literal that `present` fell through.
# --------------------------------------------------------------------------------------------


def test_f21_verify_run_recognises_every_corpus_condition():
    """A `-present` directory matched no suffix, so endpoints were never re-derived."""

    for condition in CORPUS_CONDITIONS:
        assert _condition_of(Path(f"official-001-{condition}")) == condition


def _minimal_run_dir(tmp_path, name: str):
    """The smallest run directory `verify` will get past its first gate."""

    run = tmp_path / name
    run.mkdir()
    (run / "records.final.jsonl").write_text(
        json.dumps(
            {"task_id": "ts-x", "arm": "bare", "success": True, "seed": 0, "abstained": False}
        )
        + "\n",
        encoding="utf-8",
    )
    return run


def test_f21_an_unrecognised_condition_records_a_skip_rather_than_passing_silently(tmp_path):
    """The defect was SILENCE, so asserting `_condition_of` returns None tests nothing.

    That was already true before the fix and after it. What changed is that the skipped
    endpoint re-derivation is now RECORDED, so a run whose directory ends in an unknown
    condition can no longer report green having checked the one thing this tool exists to check.
    """

    findings = verify(_minimal_run_dir(tmp_path, "official-001-nosuchcondition"))
    assert any("endpoints NOT re-derived" in line for line in findings.skipped), (
        f"an unrecognised condition must record a skip; skipped={findings.skipped}"
    )
    assert _condition_of(Path("official-001-nosuchcondition")) is None


def test_f21_a_present_run_is_no_longer_the_unrecognised_case(tmp_path):
    """`present` was the condition that fell through the literal, which is why it was found.

    The recognition assertion has to come first. Checking only that the "no known condition"
    skip is absent passes vacuously against the pre-fix code, where no skip was ever recorded
    for any reason: an absence is not evidence when the mechanism producing it did not exist.
    """

    assert _condition_of(Path("official-001-present")) == "present"
    findings = verify(_minimal_run_dir(tmp_path, "official-001-present"))
    assert not any("ends in no known condition" in line for line in findings.skipped)


@pytest.mark.parametrize(
    "path", ["scripts/prepare_recall_corpora.py", "scripts/launch_official.sh"]
)
def test_f22_f23_no_script_restates_the_condition_list(path):
    """Each restatement is a place a new condition gets silently dropped."""

    text = (REPO / path).read_text(encoding="utf-8")
    assert "absent,superseded,contradictory,adjacent" not in text, (
        f"{path} still hardcodes the adversarial four; derive it from CORPUS_CONDITIONS"
    )
    assert "CORPUS_CONDITIONS" in text


# --------------------------------------------------------------------------------------------
# F-09: miss rows padded the "what beats gold" histogram with an arbitrary top-k prefix.
# --------------------------------------------------------------------------------------------


def test_f09_the_two_populations_are_reported_separately(tmp_path, monkeypatch):
    """70 of 84 entries (83%) in a committed artifact came from queries that found no gold.

    Driven through `probe` over a fixture corpus with one HIT task and one MISS task, because the
    first version of this test read `retrieval_probe.py` as text and asserted three literal
    substrings, one of them the implementation line verbatim. That restates the implementation
    instead of the behaviour: it breaks on reformatting and it would pass against code that holds
    the string while aggregating wrongly somewhere else. F-09 is a high-stakes P1 and deserves
    better than a grep.
    """

    import scripts.retrieval_probe as probe

    corpus = tmp_path / "corpus"
    (corpus / "sessions" / "ts-hit").mkdir(parents=True)
    (corpus / "distractors").mkdir(parents=True)

    def write(path, text):
        # `content`, because that is one of `scripts.audit_corpus.TEXT_FIELDS`. A fixture written
        # with a `text` key reads back as an EMPTY document, so every task misses and the result
        # looks exactly like a ranking failure. Worth stating plainly: the probe cannot tell an
        # empty corpus from a hard one, and neither could I for two runs of this test.
        path.write_text(
            json.dumps({"role": "assistant", "content": text}) + "\n", encoding="utf-8"
        )

    write(corpus / "sessions" / "ts-hit" / "p01.jsonl", "alpha alpha alpha the governing memo")
    for index in range(4):
        write(corpus / "distractors" / f"d{index:03d}.jsonl", "beta beta beta unrelated prose")
    CorpusManifest.build(corpus)

    class _Task:
        def __init__(self, task_id, prompt):
            self.task_id, self.prompt = task_id, prompt

    # `ts-miss` has a gold document that NO query can reach, so it is a miss row; `ts-hit` is
    # retrievable. One of each is the whole point: the defect was summing their tier histograms.
    (corpus / "sessions" / "ts-miss").mkdir()
    write(corpus / "sessions" / "ts-miss" / "p01.jsonl", "zeta zeta zeta")
    CorpusManifest.build(corpus)
    monkeypatch.setattr(
        probe,
        "discover_tasks",
        lambda: [_Task("ts-hit", "alpha"), _Task("ts-miss", "beta")],
    )

    result = probe.probe(corpus, "bm25", "unused", top=3)
    summary, rows = result["summary"], {r["task_id"]: r for r in result["per_task"]}

    assert rows["ts-hit"]["rank"] is not None, "the fixture must produce one hit row"
    assert rows["ts-miss"]["rank"] is None, "the fixture must produce one miss row"

    # The behaviour: a miss row contributes to `miss_topk_tiers` and to NOTHING in
    # `competitor_tiers`, and each histogram publishes the population it was taken over.
    assert rows["ts-miss"]["competitor_tiers"] == {}
    assert rows["ts-miss"]["miss_topk_tiers"], "a miss must still report what outranked nothing"
    assert rows["ts-hit"]["miss_topk_tiers"] == {}

    assert summary["competitor_tiers_n_queries"] == 1
    assert summary["miss_topk_tiers_n_queries"] == 1
    assert sum(summary["competitor_tiers"].values()) == sum(
        rows["ts-hit"]["competitor_tiers"].values()
    ), "the aggregate must be the hit rows alone"
    assert sum(summary["miss_topk_tiers"].values()) == sum(
        rows["ts-miss"]["miss_topk_tiers"].values()
    )


# --------------------------------------------------------------------------------------------
# F-04b: the vendor tokenizer's count is a SECOND, independent refusal.
#
# Raised by the 2026-08-30 anti-regression pass, which correctly noted that this rode along with
# F-04's fix and had neither a finding ID nor a test. It stays rather than being trimmed, because
# F-04's harm is "the ceiling under-estimates paid spend" and the corrected character heuristic
# still under-estimates 19 of 200 real windows: its own docstring refuses to claim a guaranteed
# bound. A ceiling that can be exceeded is not a ceiling. It is separable, so it is named
# separately and tested here.
# --------------------------------------------------------------------------------------------


class _FakeVoyageClient:
    """Stands in for `voyageai.Client`, so the gate is exercised without a key or a paid call."""

    def __init__(self, counted, *, raises=False, absent=False):
        self._counted = counted
        self._raises = raises
        if not absent:
            self.count_tokens = self._count_tokens

    def _count_tokens(self, texts, model=None):
        if self._raises:
            raise RuntimeError("vendor client says no")
        return self._counted

    def embed(self, batch, model=None, input_type=None):
        raise AssertionError("embed must never be reached once the ceiling refuses")


def _voyage_with(monkeypatch, client, *, max_tokens):
    """Build a Voyage backend against a fake client, skipping only the construction it needs."""

    import scripts.retrieval_probe as probe

    monkeypatch.setenv("VOYAGE_API_KEY", "not-a-real-key")
    backend = object.__new__(probe.Voyage)
    backend.client = client
    backend.model = "voyage-4"
    texts = ["short text"]
    counted = backend._count_tokens(texts)
    if counted is not None:
        probe.Voyage._refuse_over_ceiling(counted, max_tokens, "vendor token count")
    return counted


def test_f04b_the_vendor_count_refuses_where_the_heuristic_would_have_passed(monkeypatch):
    """The case that makes this gate worth keeping: a short string the heuristic clears."""

    from scripts.retrieval_probe import estimate_tokens

    assert estimate_tokens(["short text"]) <= 100, "the heuristic must clear this input"
    with pytest.raises(SystemExit, match="vendor token count"):
        _voyage_with(monkeypatch, _FakeVoyageClient(1_000_000), max_tokens=100)


def test_f04b_a_count_under_the_ceiling_does_not_refuse(monkeypatch):
    assert _voyage_with(monkeypatch, _FakeVoyageClient(50), max_tokens=100) == 50


@pytest.mark.parametrize(
    "client", [_FakeVoyageClient(0, raises=True), _FakeVoyageClient(0, absent=True)]
)
def test_f04b_degrades_to_the_heuristic_rather_than_crashing(monkeypatch, client):
    """A spend guard that crashes is worse than one that proceeds on the weaker guarantee.

    Both degradations are reported on stderr rather than swallowed, which is what lets a reader
    tell a ceiling enforced by the tokenizer from one enforced only by the character heuristic.
    """

    assert _voyage_with(monkeypatch, client, max_tokens=100) is None


# --------------------------------------------------------------------------------------------
# F-28, SECOND ATTEMPT. The first fix was green, passed lint, passed the anti-regression pass,
# and was wrong: it applied the session floor to an EXISTENCE test. Caught by the architect gate.
# --------------------------------------------------------------------------------------------


def test_f28_a_task_solved_only_by_a_thin_arm_is_not_on_the_floor():
    """`ts-log-mask`: oracle_memory 3/3, every other arm 0 of 56. The largest headroom in the pool.

    The first fix filed it under FLOOR, which the tool prints as "no arm has solved them yet",
    and `docs/RETRIEVAL_DIFFICULTY.md` published that sentence. A thin arm is weak evidence about
    a RATE and perfectly good evidence that a solution EXISTS; only the first of those is what
    MIN_SESSIONS is for.
    """

    assert verdict(baseline=0.0, sessions=20, any_failure=True, ever_solved=True) == (
        "BENEFIT-ONLY"
    )
    assert verdict(baseline=0.0, sessions=20, any_failure=True, ever_solved=False) == "FLOOR"


def test_f28_the_floor_is_symmetric_with_the_damage_side():
    """`any_failure` is an existence test over every session of every arm; so is the floor test.

    Gating one and not the other made benefit capacity harder to demonstrate than damage
    capacity, which is a thumb on the scale in the direction of "memory does not help".
    """

    # One success, one session, nowhere near MIN_SESSIONS: off the floor.
    assert verdict(baseline=0.0, sessions=99, any_failure=True, ever_solved=True) != "FLOOR"
    # One failure, likewise, is enough for damage capacity at a perfect baseline.
    assert verdict(baseline=1.0, sessions=99, any_failure=True, ever_solved=True) == (
        "DAMAGE-ONLY"
    )
    assert verdict(baseline=1.0, sessions=99, any_failure=False, ever_solved=True) == (
        "NO-CAPACITY"
    )


def test_f28_the_row_that_feeds_the_verdict_counts_every_arm(monkeypatch, capsys):
    """⛔ THE test for F-28, at the layer the rejected fix actually lived in.

    Attempt 1 left `verdict()` byte-identical to pre-audit. The defect was entirely in `main()`:
    `best` was computed over session-gated arms and passed into the unchanged `best_rate`
    parameter. So every test that calls `verdict()` directly, however carefully written, is blind
    to it. Measured rather than argued: reintroducing the bug as
    `ever_solved = any(v for arm in eligible for v in arms[arm])` leaves all 40 of this file's
    other tests GREEN while `ts-log-mask` returns to FLOOR and the tool reprints the sentence
    this project spent a paragraph retracting.

    The shape below is `ts-log-mask`'s: a baseline arm at 0/20, a second eligible arm at 0/30,
    and a THIN arm at 3/3. The thin arm is the only evidence that the task is solvable at all.
    """

    import scripts.task_admission as admission

    pooled = {
        "ts-log-mask": {
            "bare": [False] * 20,
            "claude_md": [False] * 30,
            "oracle_memory": [True] * 3,
        }
    }

    class _Task:
        task_id, kind = "ts-log-mask", "primary"

    monkeypatch.setattr(admission, "load_records", lambda: (pooled, ["fake-run"], 0))
    monkeypatch.setattr(admission, "discover_tasks", lambda: [_Task()])
    monkeypatch.setattr("sys.argv", ["task_admission"])
    admission.main()

    printed = capsys.readouterr().out
    assert "FLOOR" not in printed, (
        "a task whose only successes come from a thin arm is NOT on the floor; the floor means "
        "no arm has ever solved it, and one success is proof that a solution exists"
    )
    assert "BENEFIT-ONLY" in printed
    # The gated rate is 0.00 and the ungated one is 1.00, and BOTH must reach the reader: a lone
    # 0.00 reads as "nothing has ever worked here", which is the opposite of the truth.
    assert "0.00|1.00" in printed


def test_f28_the_session_floor_still_applies_where_a_rate_is_read_as_evidence():
    """The finding was real. A rate resting on one session must not read like one resting on 30."""

    from scripts.task_admission import MIN_SESSIONS

    assert MIN_SESSIONS == 6
    assert verdict(baseline=0.5, sessions=MIN_SESSIONS - 1, any_failure=True, ever_solved=True) == (
        "THIN"
    )


def test_f28_the_floor_test_is_equivalent_to_the_pre_audit_one_everywhere_it_is_reachable():
    """"Restores the previous behaviour" is a claim; this is the check behind it.

    Exhaustive over every arms-dict of up to three arms holding up to three outcomes each. The
    old form and the new one agree everywhere except the shapes where NO arm has a single
    session, which cannot reach the FLOOR branch: getting there requires a baseline arm with at
    least MIN_SESSIONS outcomes, and those outcomes are in the pool being tested.
    """

    from itertools import product

    def pre_audit_floor(arms):
        best = max((sum(v) / len(v) for v in arms.values() if v), default=None)
        return best is not None and best <= 0.0

    def current_floor(arms):
        return not any(x for values in arms.values() for x in values)

    unreachable_only = True
    for n_arms in range(4):
        for lengths in product(range(4), repeat=n_arms):
            for bits in product(*[list(product([False, True], repeat=n)) for n in lengths]):
                arms = {f"a{i}": list(bits[i]) for i in range(n_arms)}
                if pre_audit_floor(arms) == current_floor(arms):
                    continue
                pooled = [x for values in arms.values() for x in values]
                # The ONLY permitted disagreement, and it cannot occur at the call site.
                assert pooled == [], f"unexpected divergence on {arms}"
                unreachable_only = unreachable_only and len(pooled) < 6
    assert unreachable_only
