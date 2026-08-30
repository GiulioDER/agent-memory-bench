"""Measure how hard a corpus is to retrieve from, with no model and no money.

    python -m scripts.retrieval_probe --corpus corpus
    python -m scripts.retrieval_probe --corpus corpus --corpus corpus/haystack/scale-25/seed-1
    python -m scripts.retrieval_probe --corpus corpus/haystack/scale-25/seed-1 --backend dense

Why this exists
---------------

Nothing in this repository measured retrieval. `hit@1 = 20/20` was quoted in preregistration 014
to justify disabling a reranker, and `docs/reviews/2026-08-30-instrument-review.md` section 4
found that number came from a corpus with too few competitors for ranking to matter. A ceiling
metric on a small corpus and a solved retrieval problem look identical, and the only way to tell
them apart is to make the corpus harder and watch whether the number moves.

So this is deliberately **not** a product benchmark. It is an instrument for the CORPUS:

* it takes the task prompt as the query, which is what a memory arm has at turn 0;
* it ranks the corpus with a fixed, stdlib, deterministic BM25, so a difficulty number today is
  comparable with the same number next month regardless of which vendors are wired up;
* it reports the RANK of the correct session, not only whether that rank was 1, because rank is
  what degrades before hit@1 does and is therefore the early warning a ceiling metric hides.

The optional dense backend (fastembed, `BAAI/bge-small-en-v1.5`) adds the semantic axis, since a
lexical ranker and an embedding ranker fail on different corpora. It is off by default: the
harness is stdlib-only on purpose and a difficulty claim should not need an environment.

What a document is, and what a hit is
--------------------------------------

Products chunk differently, so scoring whole 10 KB transcripts would measure chunking rather
than the corpus. Both backends therefore split every session into overlapping word windows,
score windows, and take a session's score to be its **best** window, which is what a real
retriever does when it returns evidence. A task's gold documents are the sessions under
``sessions/<task_id>/``; a hit at k means at least one of them is in the top k.

For a `xs-*` synthesis task no single session suffices, so `all_shards@k` is reported beside
`hit@k`: finding one half of a two-session fact is not finding the fact.

Scoring a PRODUCT instead of the corpus: ``--arm``
--------------------------------------------------

    python -m scripts.retrieval_probe --corpus corpus --arm fs_grep
    python -m scripts.retrieval_probe --corpus corpus --arm recall --namespace <tenant>

By default this measures the corpus. With ``--arm`` it measures a product, by asking the adapter
for its own ranked list through ``MemoryAdapter.search`` and scoring that against the same gold
labels. Everything else is unchanged, which is the point: the hit@k, the competitor tiers and
the gold labelling are the same code for a vendor as for BM25.

⚠️ **Two things about an arm number are not the same as a backend number, and neither is
cosmetic.**

1. **``gating`` decides what question is being answered.** ``served`` is retrieval as the product
   is sold: its threshold applied, abstention possible. ``raw`` is the underlying ranking with
   the gate bypassed. Each arm supports only what it truthfully has, and the two are never pooled
   silently: `recall` answers ``served`` only, because a ``raw`` list would need
   ``RECALL_TRUST_MODE`` moved off the frozen config; `fs_grep` answers ``raw`` only, because it
   is a directory and ``grep`` and has no trust policy to apply.
2. **An arm's list is truncated at ``--top``, so ``miss`` means "not in the top k"**, while for
   `bm25` and `voyage` it means "not retrieved at all". The columns look identical and are not.
   The run prints this every time rather than relying on anyone reading this paragraph.

An abstention is counted separately and scored as a miss, because a product that declined has
retrieved nothing ON PURPOSE and that is a different fact from a ranking that failed.

Reading the output
------------------

``competitors_above_gold`` is the count of wrong sessions ranked above the first right one, and
``competitor_tiers`` says which tier they came from. That second field is what says whether a
big corpus is actually hard or merely big: if every competitor is a background session about
hive inspections, the haystack has volume and no difficulty.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.adapters.base import GATINGS, CorpusManifest, resolve_corpus_path
from harness.tasks import discover_tasks
from scripts.audit_corpus import readable_text

#: Window size and stride in words. 160/120 gives roughly five windows per recorded session,
#: which lands the window count in the same range as the chunk counts the instrument review
#: quoted for the real corpora (951 to 1,129), so a window count here is readable against them.
WINDOW_WORDS = 160
WINDOW_STRIDE = 120

#: Okapi BM25's usual constants. Fixed rather than tuned: a difficulty instrument that is tuned
#: per corpus measures the tuning.
BM25_K1 = 1.2
BM25_B = 0.75

_TOKEN = re.compile(r"[a-z0-9_]+")


def tokenise(text: str) -> list[str]:
    return [token for token in _TOKEN.findall(text.lower()) if len(token) > 1]


@dataclass(frozen=True)
class Window:
    doc: str
    text: str


def windows_for(text: str) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    out = []
    for start in range(0, max(1, len(words)), WINDOW_STRIDE):
        out.append(" ".join(words[start : start + WINDOW_WORDS]))
        if start + WINDOW_WORDS >= len(words):
            break
    return out


def load_windows(corpus_root: Path) -> list[Window]:
    manifest = CorpusManifest.load(corpus_root)
    out: list[Window] = []
    for rel in sorted(manifest.sessions):
        # `resolve_corpus_path` exists for this join and `CorpusManifest.verify` already uses it;
        # this function called neither, so a manifest entry of `../..` was read straight off
        # disk. A manifest is a file, and a corpus root can come from a vendor's staging area.
        text = readable_text(resolve_corpus_path(corpus_root, rel))
        for window in windows_for(text):
            out.append(Window(doc=rel, text=window))
    return out


class BM25:
    """Okapi BM25 over the windows. Pure stdlib, so this runs anywhere the harness runs.

    ⛔ This is the SECOND BM25 in this repository, and it is not the same ranker as
    `harness/retrieval.py`: they differ in `k1`, in the stoplist, in the tokenizer and in whether
    query terms are deduplicated. Finding F-24 of the 2026-08-30 audit says so, and the
    duplication is NOT fixed, deliberately. Every number published under preregistrations 015,
    016 and 018 was measured on THIS one, so collapsing the two would change committed values
    under a committed record, and that is a decision for the person who owns those records rather
    than something an audit may do on its own. Anything comparing a number from here against one
    from `harness/retrieval.py` is comparing two rankers."""

    name = "bm25"

    def __init__(self, windows: list[Window]) -> None:
        self.windows = windows
        self.tokens = [tokenise(window.text) for window in windows]
        self.lengths = [len(tokens) for tokens in self.tokens]
        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for index, tokens in enumerate(self.tokens):
            for term, count in Counter(tokens).items():
                self.postings[term].append((index, count))
        total = len(windows)
        self.idf = {
            term: math.log(1.0 + (total - len(posting) + 0.5) / (len(posting) + 0.5))
            for term, posting in self.postings.items()
        }

    def scores(self, query: str) -> dict[int, float]:
        out: dict[int, float] = defaultdict(float)
        for term in set(tokenise(query)):
            posting = self.postings.get(term)
            if not posting:
                continue
            idf = self.idf[term]
            for index, count in posting:
                length = self.lengths[index] or 1
                denominator = count + BM25_K1 * (
                    1 - BM25_B + BM25_B * length / (self.avg_length or 1)
                )
                out[index] += idf * count * (BM25_K1 + 1) / denominator
        return out


class Dense:
    """fastembed over the same windows. Optional, and imported only when asked for."""

    name = "dense"

    def __init__(self, windows: list[Window], model: str) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as error:  # pragma: no cover - environment dependent
            raise SystemExit(
                "the dense backend needs fastembed: pip install fastembed. The bm25 backend "
                "needs nothing and is the one every difficulty claim in this repository uses."
            ) from error
        import numpy

        self.numpy = numpy
        self.windows = windows
        self.model = TextEmbedding(model_name=model)
        vectors = list(self.model.embed([window.text for window in windows], batch_size=64))
        self.matrix = numpy.vstack(vectors)
        norms = self.numpy.linalg.norm(self.matrix, axis=1, keepdims=True)
        self.matrix = self.matrix / self.numpy.where(norms == 0, 1, norms)

    def scores(self, query: str) -> dict[int, float]:
        vector = next(iter(self.model.query_embed([query])))
        vector = vector / (self.numpy.linalg.norm(vector) or 1)
        similarities = self.matrix @ vector
        return {index: float(value) for index, value in enumerate(similarities)}


class Voyage:
    """Hosted embeddings, so no model runs on any machine of ours.

    This is the backend that answers the question `bm25` cannot: whether near-misses built out of
    shared surface vocabulary also fool a SEMANTIC ranker. It uses the same family the production
    memory corpus is built with (`voyage-4`, 1024 dimensions), so a difficulty number here is
    read against a real store rather than against a toy embedder.

    Two guards, because this one spends money:

    * ``--max-tokens`` is a hard refusal, not a warning. The estimate is printed and the run
      stops before the first request if the corpus is bigger than the caller expected. A probe
      that silently costs ten times its estimate is worse than one that refuses.
    * document and query embeddings use the API's own ``input_type``, which is not cosmetic:
      an asymmetric model scored with the wrong side is a quiet quality loss that would read
      here as corpus difficulty.
    """

    name = "voyage"

    #: The API caps a request by count and by tokens. 96 windows of 160 words sits under both
    #: with room for the longest window in the corpus.
    BATCH = 96

    def __init__(self, windows: list[Window], model: str, max_tokens: int) -> None:
        self.windows = windows
        self.model = model
        texts = [window.text for window in windows]

        # ⛔ The cheap ceiling runs FIRST, before any import. It used to sit fifteen lines below
        # `import voyageai`, which pulls transformers and sentence_transformers through
        # langchain_text_splitters and costs about 41 seconds (measured). That made the refusal
        # unreachable on a host without the client, defeating the very property the ordering was
        # written for, and made the test that pins the refusal the single most expensive test in
        # the suite at 8.5% of its runtime.
        estimate = estimate_tokens(texts)
        print(
            f"voyage: {len(windows)} windows, about {estimate:,} tokens to embed (pre-flight)",
            file=sys.stderr,
        )
        self._refuse_over_ceiling(estimate, max_tokens, "pre-flight estimate")

        try:
            import voyageai
        except ImportError as error:  # pragma: no cover - environment dependent
            raise SystemExit(
                "the voyage backend needs the voyageai client: pip install voyageai, and "
                "VOYAGE_API_KEY in the environment. Run it where the key already lives."
            ) from error
        import numpy

        self.numpy = numpy
        if not os.environ.get("VOYAGE_API_KEY"):
            raise SystemExit(
                "VOYAGE_API_KEY is not set. This backend calls a paid API and will not guess "
                "at credentials; run it on the host whose environment already has the key."
            )
        self.client = voyageai.Client()

        # ---- F-04b, the second half of F-04's fix and separable from it -------------------
        #
        # The AUTHORITATIVE ceiling, from the vendor's own tokenizer, before a single paid call.
        # The pre-flight estimate above is a character heuristic and is not a guaranteed bound:
        # the worst window in this corpus carries 2.075x the tokens it predicts. Asking the
        # client what it will actually bill costs nothing and is the only number that can hold
        # the promise `--max-tokens` makes.
        counted = self._count_tokens(texts)
        if counted is not None:
            print(f"voyage: {counted:,} tokens by the vendor tokenizer", file=sys.stderr)
            self._refuse_over_ceiling(counted, max_tokens, "vendor token count")

        chunks = []
        for start in range(0, len(texts), self.BATCH):
            batch = texts[start : start + self.BATCH]
            # Converted per batch rather than accumulating list[list[float]] for the whole
            # corpus: 23,204 windows of 1,024 boxed Python floats is ~776 MB against a 95 MB
            # matrix, and this host has starved an arm at 421 MB free before now.
            chunks.append(
                numpy.asarray(
                    self.client.embed(batch, model=model, input_type="document").embeddings,
                    dtype="float32",
                )
            )
            print(
                f"  embedded {min(start + self.BATCH, len(texts)):>6} / {len(texts)}",
                file=sys.stderr,
            )
        self.matrix = numpy.vstack(chunks) if chunks else numpy.zeros((0, 1), dtype="float32")
        norms = numpy.linalg.norm(self.matrix, axis=1, keepdims=True)
        self.matrix /= numpy.where(norms == 0, 1, norms)

    @staticmethod
    def _refuse_over_ceiling(tokens: int, ceiling: int, label: str) -> None:
        if tokens > ceiling:
            raise SystemExit(
                f"refusing to spend: {label} of {tokens:,} tokens is over the --max-tokens "
                f"ceiling of {ceiling:,}. Raise it deliberately or probe a smaller corpus."
            )

    def _count_tokens(self, texts: list[str]) -> int | None:
        """The vendor's own count, or None when this client build cannot supply one.

        None is reported rather than silently skipped: a ceiling enforced only by the heuristic
        is a weaker guarantee than one enforced by the tokenizer, and the run says which it got.
        """

        counter = getattr(self.client, "count_tokens", None)
        if counter is None:  # pragma: no cover - depends on the installed client version
            print(
                "voyage: this client exposes no count_tokens; the ceiling rests on the "
                "character heuristic alone, which is NOT a guaranteed upper bound",
                file=sys.stderr,
            )
            return None
        try:  # pragma: no cover - network/version dependent
            return int(counter(texts, model=self.model))
        except Exception as error:  # noqa: BLE001 - see below
            # Blind catch on purpose. This is a best-effort STRENGTHENING of a ceiling that is
            # already enforced by the heuristic above, and the vendor client's failure modes vary
            # by version and by network condition. Narrowing it would mean an unanticipated
            # exception type turned a spend guard into a crash after the credential check and
            # before any refund, which is worse than proceeding on the weaker guarantee. The
            # degradation is printed rather than swallowed.
            print(f"voyage: count_tokens unavailable ({error}); heuristic only", file=sys.stderr)
            return None

    def scores(self, query: str) -> dict[int, float]:
        vector = self.numpy.array(
            self.client.embed([query], model=self.model, input_type="query").embeddings[0],
            dtype="float32",
        )
        vector = vector / (self.numpy.linalg.norm(vector) or 1)
        return {index: float(value) for index, value in enumerate(self.matrix @ vector)}


#: Characters per token, used for the pre-credential estimate. Measured 2026-08-30 over
#: `load_windows(Path("corpus"))`: 1,220 windows, 1,112,424 chars, 315,734 real cl100k_base
#: tokens, so **3.523 chars/token corpus-wide**. 3.0 buys a 17% margin on that total.
#:
#: Re-measure:
#:     python -c "import sys;sys.path.insert(0,'.');from pathlib import Path;import tiktoken;\
#:     from scripts.retrieval_probe import load_windows;e=tiktoken.get_encoding('cl100k_base');\
#:     t=[w.text for w in load_windows(Path('corpus'))];print(sum(len(e.encode(x)) for x in t))"
CHARS_PER_TOKEN = 3.0


def estimate_tokens(texts) -> int:
    """A conservative pre-flight estimate, on CHARACTERS. Not a guaranteed upper bound.

    ⛔ This counted WORDS times 1.35 and its docstring claimed it "errs high". It errs LOW.
    Measured 2026-08-30 against cl100k_base on this repository's own corpus: 247,480 estimated
    against 315,734 real, a ratio of 0.784. The cause is that the corpus is agent transcripts,
    so it carries paths, identifiers and `json.dumps` blobs at 6.07 chars/word against English
    prose's ~5.1, and a word-based constant cannot track character density at all: a single
    4,000-character run with no spaces estimated as ONE token. A spend gate computed from it let
    a run bill about 1.27x what was approved.

    ⚠️ **Characters do not make it a guarantee either, and the docstring will not claim one.**
    Measured on the same corpus, the worst individual window carries 2.075x the tokens
    ``chars/3.0`` predicts, because BPE can emit a token per character on unusual bytes. The
    corpus-wide margin is 17%; a pathological corpus could still exceed it. That is why the
    ceiling is now enforced TWICE: this cheap estimate before the credential, so it stays
    checkable on a host with no key, and the vendor's own `count_tokens` after the client is
    built and before the first paid call, which is authoritative.
    """

    return int(sum(len(text) for text in texts) / CHARS_PER_TOKEN)


class ArmBackend:
    """A product's OWN ranked list, instead of one of this probe's rankers.

    This is what turns a corpus difficulty number into a statement about a vendor. Everything
    else in this file (gold labels, windows, hit@k, MRR, competitor tiers) is backend agnostic
    already; the missing piece was that no adapter could be asked what it would have retrieved,
    because every arm's retrieval happens inside its own MCP server and the harness only ever saw
    tool calls in a transcript.

    ⚠️ **`gating` is not a detail and is carried into every result.** recall answers `served`
    only, with its certified threshold applied and abstention possible, because a `raw` list
    would need `RECALL_TRUST_MODE` overridden away from the frozen config. `fs_grep` answers
    `raw` only, because it is a directory and `grep` and has no trust policy to apply. Those are
    different questions, both legitimate, and a table that pools them without saying so is
    measuring two things under one heading.
    """

    def __init__(self, adapter, namespace: str, gating: str, limit: int) -> None:
        if gating not in adapter.supported_gatings:
            raise SystemExit(
                f"{adapter.name} supports gating {adapter.supported_gatings}, not {gating!r}. "
                f"Pass --gating with one it supports; the difference is what is being measured, "
                f"not a formality."
            )
        self.adapter = adapter
        self.namespace = namespace
        self.gating = gating
        self.limit = limit
        self.name = f"{adapter.name}:{gating}"
        self.abstentions = 0
        #: Corpus document keys, bound by `probe` before the first query. Everything below is
        #: about whether the arm's identifiers are the SAME identifiers, which is a different
        #: failure from ranking badly and must never be published as one.
        self.documents: set[str] = set()
        self.hits_returned = 0
        self.hits_joined = 0
        self.unjoinable_examples: list[str] = []

    def bind_corpus(self, documents: set[str]) -> None:
        self.documents = set(documents)

    def ranking(self, query: str) -> list[tuple[str, float]]:
        result = self.adapter.search(
            self.namespace, query, gating=self.gating, limit=self.limit
        )
        if result.abstained:
            # An abstention is a DECISION, not an empty index, and the two must not read alike.
            # A product that declines here has retrieved nothing on purpose and should score as a
            # miss, with the count reported so nobody reads the miss as a ranking failure.
            self.abstentions += 1
        ranked = [(hit.source_path, hit.score) for hit in result.hits]
        for source, _score in ranked:
            self.hits_returned += 1
            if source in self.documents:
                self.hits_joined += 1
            elif len(self.unjoinable_examples) < 5:
                self.unjoinable_examples.append(source)
        return ranked

    def assert_joinable(self) -> None:
        """Refuse to publish a number when the arm's identifiers are not the corpus's.

        A total join failure and a product that retrieves nothing produce the SAME hit@1 of
        0.000, and only one of them is a fact about the vendor. recall indexes rendered ``.md``
        filenames while the manifest is keyed by ``.jsonl`` transcript paths, so this is not
        hypothetical: it is the default outcome until the path mapping is settled, and a run that
        did not check would have published a structural zero as a measured one.

        Silence on a PARTIAL failure would be the same mistake at smaller scale, so the counts go
        into the summary AND are printed by `main` with a `[!!]` whenever the rate is below 1.0.
        This is deliberately not a refusal: a product's store can legitimately hold documents
        outside the probed corpus, so refusing on any unjoinable hit would refuse a legitimate
        run. But an unjoinable hit still occupies a rank and pushes gold down, so a partial
        failure biases the score DOWNWARD against the vendor, and every rate is a lower bound.
        """

        if self.hits_returned and not self.hits_joined:
            raise SystemExit(
                f"{self.name}: {self.hits_returned} hit(s) returned and NONE join the corpus "
                f"manifest, so every rank is unscoreable and hit@k would be a structural zero "
                f"rather than a measurement. Examples: {self.unjoinable_examples}. Fix the "
                f"identifier mapping before reporting this arm."
            )


def build_arm(name: str, corpus_root: Path, gating: str | None, namespace: str | None, top: int):
    """Construct one arm's adapter and point it at ``corpus_root``.

    `fs_grep` is ingested here into a temporary staging directory, because its whole store IS the
    rendered corpus and building it takes a second. `recall`'s tenant is built out of band
    against a frozen manifest, so a namespace must be given rather than guessed: pointing this at
    the wrong tenant would silently score a different corpus, which is the same class of error as
    scoring a plant as gold.
    """

    import tempfile

    from adapters.fs_grep.adapter import FsGrepAdapter
    from adapters.recall.adapter import RecallAdapter

    bundle = REPO / "corpus" / "claude_md_bundle_smoke.md"
    if name == "fs_grep":
        adapter = FsGrepAdapter(staging_root=tempfile.mkdtemp(), base_prompt_file=bundle)
        namespace = namespace or "probe"
        adapter.ingest(CorpusManifest.load(corpus_root), namespace)
    elif name == "recall":
        if not namespace:
            raise SystemExit(
                "--arm recall needs --namespace: its tenant is built out of band and this "
                "cannot verify that an unnamed one holds the corpus being probed"
            )
        adapter = RecallAdapter(staging_root=tempfile.mkdtemp(), base_prompt_file=bundle)
    else:  # pragma: no cover - argparse constrains this
        raise SystemExit(f"unknown arm {name!r}")
    return ArmBackend(adapter, namespace, gating or adapter.supported_gatings[0], top)


def rank_documents(backend, windows: list[Window], query: str) -> list[tuple[str, float]]:
    """Score windows, keep each document's best window, and rank documents by it."""

    best: dict[str, float] = {}
    for index, score in backend.scores(query).items():
        doc = windows[index].doc
        if score > best.get(doc, float("-inf")):
            best[doc] = score
    return sorted(best.items(), key=lambda item: (-item[1], item[0]))


def plant_files(corpus_root: Path) -> tuple[dict[str, set[str]], dict[str, bool]]:
    """Which files under ``sessions/<task>/`` are PLANTS, read from ``condition.json``.

    ⛔ Without this the probe is confidently wrong on any condition corpus, and silently so.
    `scripts/assemble_condition_corpus.py` writes a planted session into
    ``sessions/<task_id>/``, in the real session's place, because that is what makes every
    adapter ingest it unchanged. This probe's gold was "the sessions under ``sessions/<task>/``",
    so on an `adjacent` or `contradictory` corpus it scored **the plant** as the correct answer
    and reported how findable the WRONG memo is. Zero misses is the tell: a condition that
    withholds the real session cannot have a gold document to miss.

    Found on 2026-08-30 by the session that owns the plants, running this probe against
    ``corpus/conditions/adjacent/seed-1``. Nothing about the haystack results changes, because a
    haystack root has no ``condition.json`` and its real sessions are copied byte for byte.
    """

    path = corpus_root / "condition.json"
    if not path.is_file():
        return {}, {}
    data = json.loads(path.read_text(encoding="utf-8"))
    plants: dict[str, set[str]] = {}
    include_real: dict[str, bool] = {}
    for task_id, entry in data.get("planted", {}).items():
        plants[str(task_id)] = {f"{name}.jsonl" for name in entry.get("plants", ())}
        include_real[str(task_id)] = bool(entry.get("include_real"))
    return plants, include_real


def tier_of(rel: str, plan: dict | None, plants: dict[str, set[str]] | None = None) -> str:
    # `sessions/smoke/` belongs to no task and is gold for nothing, so counting it as signal
    # would report another task's precursor and a bring-up transcript as the same kind of
    # competitor. `scripts/audit_corpus.py` was fixed for exactly this directory once already.
    if rel.startswith("sessions/smoke/"):
        return "smoke"
    if rel.startswith("sessions/"):
        if plants:
            parts = rel.split("/")
            if len(parts) >= 3 and parts[2] in plants.get(parts[1], ()):
                return "plant"
        return "other-task-signal"
    if rel.startswith("distractors/"):
        return "real-distractor"
    if plan is not None:
        entry = plan.get("sessions", {}).get(rel)
        if entry:
            return str(entry["tier"])
    return "unknown"


def _median_rank(scored: list[dict]) -> int | None:
    """The median rank, or None when the median observation is a miss.

    A miss has no rank. Sorting it as `10**9` keeps it correctly at the end, but that sentinel
    was then published verbatim as `median_rank` and printed in the results table, where it
    reads as a number rather than as "at least half these queries found nothing".

    Boundary, stated because it is easy to get wrong when reading this back: for even `n` the
    upper-middle element is taken, so exactly 50% misses returns None. That is the honest
    direction (it declines to name a median rather than reporting the better half's), and it is
    half a step stricter than "above 50%" would be.
    """

    if not scored:
        return None
    ranks = sorted(row["rank"] or 10**9 for row in scored)
    middle = ranks[len(scored) // 2]
    return None if middle == 10**9 else middle


def _cell(value, width: int, spec: str = "") -> str:
    """Format a summary cell that is legitimately absent, without crashing the table."""

    if value is None:
        return f"{'n/a':>{width}}"
    return f"{value:>{width}{spec}}"


def probe(
    corpus_root: Path,
    backend_name: str,
    model: str,
    top: int,
    max_tokens: int = 0,
    arm: object | None = None,
) -> dict:
    plan_path = corpus_root / "haystack.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else None
    if arm is not None:
        # An arm ranks whole DOCUMENTS itself, so nothing here is windowed and the summary
        # says 0 rather than borrowing the corpus's count. The comment that stood here promised
        # the opposite ("the window count below is the corpus's, reported for comparability"),
        # and two committed artifacts publish `"windows": 0` against it:
        # `results/retrieval/arm-fs-grep-25x.json` and `arm-fs-grep-base.json`. Reporting 0 is
        # correct and comparing it against a ranker's window count is meaningless, so the number
        # is left alone and the claim is withdrawn.
        windows = []
        documents = set(CorpusManifest.load(corpus_root).sessions)
        backend = arm
        backend.bind_corpus(documents)
    else:
        windows = load_windows(corpus_root)
        documents = {window.doc for window in windows}
        if backend_name == "bm25":
            backend = BM25(windows)
        elif backend_name == "voyage":
            backend = Voyage(windows, model, max_tokens)
        else:
            backend = Dense(windows, model)
    plants, include_real = plant_files(corpus_root)

    rows = []
    withheld: list[str] = []
    for task in sorted(discover_tasks(), key=lambda t: t.task_id):
        under = {rel for rel in documents if rel.startswith(f"sessions/{task.task_id}/")}
        # A planted file sits in the real session's place, so it is a COMPETITOR here, never the
        # answer. Scoring it as gold is what made this probe report a condition corpus as if the
        # wrong memo were the right one.
        planted = {
            rel for rel in under if rel.split("/")[-1] in plants.get(task.task_id, set())
        }
        gold = under - planted
        if not under:
            continue
        # `condition.json` says whether the real session was kept. If that disagrees with what is
        # on disk, one of the two is lying about which condition this corpus is, and scoring it
        # either way would publish a number for a condition that was never built.
        if task.task_id in include_real and bool(gold) != include_real[task.task_id]:
            raise SystemExit(
                f"{corpus_root.as_posix()}: condition.json says include_real="
                f"{include_real[task.task_id]} for {task.task_id}, but "
                f"{len(gold)} non-planted session(s) are on disk. Rebuild the condition corpus; "
                f"a probe cannot say which of the two is right."
            )
        ranking = (
            backend.ranking(task.prompt)
            if isinstance(backend, ArmBackend)
            else rank_documents(backend, windows, task.prompt)
        )
        order = [rel for rel, _ in ranking]
        plant_positions = [index + 1 for index, rel in enumerate(order) if rel in planted]
        if not gold:
            # The condition withheld the governing session. There is no right answer to find, so
            # this task contributes to no hit@k. Reporting where the PLANT ranks is the useful
            # thing left, and it is the pre-flight a condition corpus actually wants: a planted
            # memo nobody can retrieve cannot mislead anybody, so that condition would be
            # measuring nothing for that task.
            withheld.append(task.task_id)
            rows.append(
                {
                    "task_id": task.task_id,
                    "gold_documents": 0,
                    "gold_withheld_by_condition": True,
                    "rank": None,
                    "all_shards_rank": None,
                    "competitors_above_gold": None,
                    "plant_rank": min(plant_positions) if plant_positions else None,
                    "competitor_tiers": {},
                }
            )
            continue
        positions = [index + 1 for index, rel in enumerate(order) if rel in gold]
        first = min(positions) if positions else None
        # TWO POPULATIONS, never one. Above a gold document that WAS retrieved, every entry is a
        # competitor that genuinely beat the right answer. On a miss there is no gold in the list,
        # so `order[:top]` is an arbitrary prefix of a ranking that failed: it says what the
        # ranker liked, not what outranked anything. Summing the two gave a "what beats gold"
        # histogram of which 70 of 84 entries (83%) in a committed artifact came from misses.
        above_gold = order[: (first - 1)] if first else []
        miss_prefix = [] if first else order[:top]
        rows.append(
            {
                "task_id": task.task_id,
                "gold_documents": len(gold),
                "gold_withheld_by_condition": False,
                "rank": first,
                "all_shards_rank": max(positions) if len(positions) == len(gold) else None,
                "competitors_above_gold": (first - 1) if first else None,
                "plant_rank": min(plant_positions) if plant_positions else None,
                "competitor_tiers": dict(
                    Counter(tier_of(rel, plan, plants) for rel in above_gold)
                ),
                # Kept, because what a failed ranking preferred is diagnostic. Named so it can
                # never be added to the line above by accident.
                "miss_topk_tiers": dict(
                    Counter(tier_of(rel, plan, plants) for rel in miss_prefix)
                ),
            }
        )
    if isinstance(backend, ArmBackend):
        backend.assert_joinable()
    scored = [row for row in rows if not row["gold_withheld_by_condition"]]

    # Every rate below is over SCORED queries: the ones that have a right answer to find. A task
    # whose governing session the condition withheld is not a miss, it is not a question.
    def hit_at(k: int) -> float:
        return sum(1 for row in scored if row["rank"] and row["rank"] <= k) / max(1, len(scored))

    synthesis = [row for row in scored if row["gold_documents"] > 1]
    plant_ranked = [row for row in rows if row["plant_rank"]]
    # What was probed, pinned to something that survives the directory being rebuilt. The only
    # provenance here was `corpus_root.as_posix()`, and `corpus/haystack/` is gitignored, so
    # every committed `results/retrieval/*.json` names a path that is not in the tree and can be
    # tied to no particular build of it. `corpus_sha256` is over the manifest, so it moves with
    # any document; `generator_sha256` and `seed` come from the haystack plan when there is one.
    manifest_digest = hashlib.sha256(
        json.dumps(
            dict(sorted(CorpusManifest.load(corpus_root).sessions.items())),
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    summary = {
        "corpus": corpus_root.as_posix(),
        "corpus_sha256": manifest_digest,
        "generator_sha256": (plan or {}).get("generator_sha256"),
        "corpus_seed": (plan or {}).get("seed"),
        "corpus_scale": (plan or {}).get("scale"),
        "backend": backend.name,
        "documents": len(documents),
        "windows": len(windows),
        "gating": getattr(backend, "gating", None),
        "abstentions": getattr(backend, "abstentions", None),
        "arm_hits_returned": getattr(backend, "hits_returned", None),
        "arm_hits_joined": getattr(backend, "hits_joined", None),
        "arm_unjoinable_examples": getattr(backend, "unjoinable_examples", None),
        "queries": len(scored),
        "gold_withheld_by_condition": sorted(withheld),
        "plants_ranked_top10": sum(1 for row in plant_ranked if row["plant_rank"] <= 10),
        # Tasks that HAVE a plant, whether or not it was retrieved. `len(plant_ranked)`
        # stood here, which excludes exactly the plants that ranked nowhere: the population
        # the sentence printed downstream is about. It made an unretrievable plant
        # invisible instead of reporting it, which is the pre-flight's whole purpose.
        # Over the rows this run actually probed, so it is the same population as
        # `plants_ranked_top10`. Counting `condition.json` entries instead would put
        # a task with a plant but no documents under `sessions/<id>/` into the
        # denominator only, since the loop above skips it before it becomes a row.
        "plants_present": sum(1 for row in rows if plants.get(row["task_id"])),
        "plants_retrieved": len(plant_ranked),
        "hit@1": round(hit_at(1), 4),
        "hit@5": round(hit_at(5), 4),
        "hit@10": round(hit_at(10), 4),
        "mrr@10": round(
            sum(1.0 / row["rank"] for row in scored if row["rank"] and row["rank"] <= 10)
            / max(1, len(scored)),
            4,
        ),
        # The sentinel sorts misses last, which is right, but publishing it would print
        # 1000000000 as a rank. Above 50% misses the median IS a miss, and `None` says so.
        "median_rank": _median_rank(scored),
        # Averaged over the queries that RETRIEVED the gold session at all. Folding a miss in as
        # zero competitors was the first version of this line and it reports a corpus as easier
        # the harder it gets, since a total failure would have contributed the smallest possible
        # number to the mean. Misses are counted, not absorbed.
        # `max(1, ...)` on an EMPTY numerator yields 0.0, so a corpus where every single query
        # missed printed `mean above 0.00`: total retrieval failure rendered as the easiest
        # possible result. There is no mean over no observations, and None is the honest value.
        "mean_competitors_above_gold": (
            round(
                sum(row["competitors_above_gold"] for row in scored if row["rank"])
                / sum(1 for row in scored if row["rank"]),
                2,
            )
            if any(row["rank"] for row in scored)
            else None
        ),
        "mean_competitors_n_queries": sum(1 for row in scored if row["rank"]),
        "misses": sum(1 for row in scored if not row["rank"]),
        "all_shards@10": (
            round(
                sum(
                    1
                    for row in synthesis
                    if row["all_shards_rank"] and row["all_shards_rank"] <= 10
                )
                / len(synthesis),
                4,
            )
            if synthesis
            else None
        ),
        # Over the queries that RETRIEVED gold, and ONLY those. `competitor_tiers_n_queries` is
        # published beside it because a histogram whose population is not stated cannot be read.
        "competitor_tiers": dict(
            sum((Counter(row["competitor_tiers"]) for row in scored if row["rank"]), Counter())
        ),
        "competitor_tiers_n_queries": sum(1 for row in scored if row["rank"]),
        "miss_topk_tiers": dict(
            sum(
                (Counter(row["miss_topk_tiers"]) for row in scored if not row["rank"]),
                Counter(),
            )
        ),
        "miss_topk_tiers_n_queries": sum(1 for row in scored if not row["rank"]),
    }
    return {"summary": summary, "per_task": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        action="append",
        default=None,
        help="a corpus root; repeat to print the difficulty curve across sizes",
    )
    parser.add_argument("--backend", choices=("bm25", "dense", "voyage"), default="bm25")
    parser.add_argument(
        "--arm",
        choices=("fs_grep", "recall"),
        default=None,
        help="score the PRODUCT's own ranked list instead of this probe's rankers. Turns a "
        "corpus difficulty number into a statement about a vendor.",
    )
    parser.add_argument(
        "--gating",
        choices=GATINGS,
        default=None,
        help="served (the trust policy the product actually serves through, threshold applied "
        "and abstention possible) or raw (ungated ranking). NOT interchangeable, and each arm "
        "supports only what it truthfully has; defaults to the arm's single supported mode.",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="the arm's store namespace or tenant. Required with --arm recall, whose tenant is "
        "built out of band; fs_grep ingests into a temporary staging directory.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="embedder id; defaults to bge-small for --backend dense and voyage-4 for voyage",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2_000_000,
        help="hard ceiling PER CORPUS for the paid voyage backend; it refuses rather than warns",
    )
    parser.add_argument(
        "--max-tokens-total",
        type=int,
        default=0,
        help="hard ceiling across every --corpus in one invocation. --corpus is repeatable, so "
        "--max-tokens alone caps each root and NOTHING caps the run. ⚠️ The default (0) derives "
        "this as --max-tokens x the number of roots, which PRESERVES that spend envelope: it "
        "makes the total visible and refusable, it does not lower it. That is deliberate, "
        "because the repeatable --corpus is the designed way to probe a difficulty curve and a "
        "stricter default would refuse the tool's normal use. Pass a real number to bound a run "
        "below N x the per-corpus ceiling.",
    )
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--out", default=None, help="write the full result to this JSON file")
    parser.add_argument("--per-task", action="store_true", help="print the per-task table too")
    args = parser.parse_args()

    top = args.top
    roots = [Path(root) for root in (args.corpus or ["corpus"])]
    model = args.model or (
        "voyage-4" if args.backend == "voyage" else "BAAI/bge-small-en-v1.5"
    )
    # The aggregate ceiling, checked BEFORE the first paid call of the first root rather than
    # discovered on the last one. Deriving the default keeps single-root behaviour identical.
    # `--arm` is excluded: an arm ranks through its own product and never constructs
    # `Voyage`, so `--arm X --backend voyage` spends nothing. Gating on the backend alone made
    # this pay a full `load_windows` pass and let it refuse a run that could not have cost
    # anything.
    priced = args.backend == "voyage" and not args.arm
    # ⚠️ The derived default preserves the pre-fix spend envelope rather than lowering it. See
    # --max-tokens-total's help: this makes the aggregate visible and refusable, which is what
    # F-50 asked for, and deliberately does not make a curve run refuse by default.
    total_ceiling = args.max_tokens_total or args.max_tokens * len(roots)
    if priced and len(roots) > 1:
        print(
            f"voyage: {len(roots)} corpora, ceiling {args.max_tokens:,} each and "
            f"{total_ceiling:,} in total",
            file=sys.stderr,
        )
    spent_estimate = 0

    results = []
    for root in roots:
        if not (root / "manifest.json").is_file():
            raise SystemExit(f"{root} has no manifest.json; it is not a corpus root")
        if priced:
            estimate = estimate_tokens([w.text for w in load_windows(root)])
            if spent_estimate + estimate > total_ceiling:
                raise SystemExit(
                    f"refusing to embed {root.as_posix()}: it would take the run to "
                    f"{spent_estimate + estimate:,} estimated tokens against a total ceiling of "
                    f"{total_ceiling:,}. Raise --max-tokens-total deliberately, or probe fewer "
                    f"roots per invocation."
                )
            spent_estimate += estimate
        arm = build_arm(args.arm, root, args.gating, args.namespace, args.top) if args.arm else None
        label = arm.name if arm is not None else f"{args.backend} ({model})"
        print(f"probing {root.as_posix()} with {label} ...", file=sys.stderr)
        results.append(probe(root, args.backend, model, args.top, args.max_tokens, arm))

    # ⛔ WRITTEN FIRST. This used to be the last statement of `main()`, downstream of every
    # print below, one of which crashes when `scored` is empty (`median_rank` None formatted
    # with `:>9`). A voyage run can cost real money, and losing its results to a formatting bug
    # in a summary table is not a trade anybody would make deliberately.
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {out.as_posix()}")

    header = (
        f"{'documents':>10} {'windows':>9} {'hit@1':>7} {'hit@5':>7} {'hit@10':>7} "
        f"{'mrr@10':>7} {'med rank':>9} {'mean above':>11} {'miss':>5}  corpus"
    )
    print(header)
    for result in results:
        s = result["summary"]
        print(
            f"{s['documents']:>10} {s['windows']:>9} {s['hit@1']:>7.3f} {s['hit@5']:>7.3f} "
            f"{s['hit@10']:>7.3f} {s['mrr@10']:>7.3f} "
            f"{_cell(s['median_rank'], 9)} {_cell(s['mean_competitors_above_gold'], 11, '.2f')} "
            f"{s['misses']:>5}  {s['corpus']}"
        )

    for result in results:
        s = result["summary"]
        if s["gating"]:
            print(
                f"\n{s['corpus']}: arm {s['backend']}, gating {s['gating']}, "
                f"{s['abstentions']} abstention(s)."
            )
            print(
                "  [!!] An arm returns at most --top hits, so `miss` here means NOT IN THE TOP "
                f"{top}, while for bm25 and voyage it means not retrieved at all. The two "
                "columns do not mean the same thing and must not be differenced."
            )
            if s["gating"] == "served":
                print(
                    "  gating=served: the product's own threshold applied and it could abstain, "
                    "so this is retrieval AS SOLD, not the underlying ranking."
                )
            else:
                print(
                    "  gating=raw: no trust policy applied. Not comparable with a served number "
                    "from another arm."
                )
        if s.get("arm_hits_returned"):
            joined, returned = s["arm_hits_joined"], s["arm_hits_returned"]
            rate = joined / returned
            print(
                f"  join rate {joined}/{returned} = {rate:.3f} of this arm's hits are corpus "
                f"documents."
            )
            if rate < 1.0:
                # ⛔ Loud, and on the human path. `assert_joinable` refuses only a TOTAL failure,
                # because a product's store can legitimately hold documents outside the probed
                # corpus. But a PARTIAL failure biases the score DOWNWARD against the vendor,
                # since an unjoinable hit still occupies a rank and pushes gold down, and that is
                # this project's own harm class. The counts were in the JSON and nowhere a reader
                # looks, which made the docstring's promise to report them untrue.
                print(
                    f"  [!!] {returned - joined} hit(s) do NOT join the corpus manifest. They "
                    f"still occupy ranks, so every rate above is a LOWER BOUND on this arm. "
                    f"Examples: {s['arm_unjoinable_examples']}"
                )
        if s["gold_withheld_by_condition"]:
            print(
                f"\n{s['corpus']}: [!!] CONDITION CORPUS. The governing session is WITHHELD "
                f"for {len(s['gold_withheld_by_condition'])} task(s), so they have no right "
                f"answer to find and are excluded from every rate above: "
                f"{', '.join(s['gold_withheld_by_condition'])}."
            )
        if s["plants_present"]:
            print(
                f"{s['corpus']}: planted memos retrieved in the top 10 for "
                f"{s['plants_ranked_top10']} of {s['plants_present']} planted task(s). A plant "
                f"nobody can retrieve cannot mislead anybody, so that condition would be "
                f"measuring nothing for those tasks."
            )
        if s["competitor_tiers"]:
            tiers = ", ".join(f"{k} {v}" for k, v in sorted(s["competitor_tiers"].items()))
            print(f"\n{s['corpus']}: wrong sessions ranked above the right one, by tier: {tiers}")
        if s["all_shards@10"] is not None:
            print(f"{s['corpus']}: all_shards@10 = {s['all_shards@10']:.3f} (xs-* tasks)")

    if args.per_task:
        print(f"\n{'task':22s} {'rank':>6} {'above':>6}  top competitor tiers")
        for result in results:
            print(f"-- {result['summary']['corpus']}")
            for row in result["per_task"]:
                # A miss row has no competitors-above-gold by construction, so printing only
                # that column would blank it. The top-k prefix is what the failed ranking
                # preferred, and it is the diagnostic for a miss; it is labelled so nobody
                # reads it as "these beat the right answer".
                shown = row["competitor_tiers"] or {
                    f"miss:{k}": v for k, v in row.get("miss_topk_tiers", {}).items()
                }
                tiers = ", ".join(f"{k}:{v}" for k, v in sorted(shown.items()))
                print(f"{row['task_id']:22s} {row['rank']!s:>6} "
                      f"{row['competitors_above_gold']!s:>6}  {tiers}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
