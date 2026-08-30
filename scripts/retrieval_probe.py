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

from harness.adapters.base import GATINGS, CorpusManifest
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
        text = readable_text(corpus_root / rel)
        for window in windows_for(text):
            out.append(Window(doc=rel, text=window))
    return out


class BM25:
    """Okapi BM25 over the windows. Pure stdlib, so this runs anywhere the harness runs."""

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
        try:
            import voyageai
        except ImportError as error:  # pragma: no cover - environment dependent
            raise SystemExit(
                "the voyage backend needs the voyageai client: pip install voyageai, and "
                "VOYAGE_API_KEY in the environment. Run it where the key already lives."
            ) from error
        import numpy

        self.numpy = numpy
        self.windows = windows
        self.model = model
        # The spend ceiling is checked BEFORE the credential, so a run that was going to cost
        # more than the caller expected is refused whether or not a key happens to be present.
        # Checking the key first would make the ceiling unreachable on any host without one,
        # which is every host where somebody would want to sanity check the estimate.
        estimate = estimate_tokens(window.text for window in windows)
        print(
            f"voyage: {len(windows)} windows, about {estimate:,} tokens to embed",
            file=sys.stderr,
        )
        if estimate > max_tokens:
            raise SystemExit(
                f"refusing to spend: estimated {estimate:,} tokens is over the --max-tokens "
                f"ceiling of {max_tokens:,}. Raise it deliberately or probe a smaller corpus."
            )
        if not os.environ.get("VOYAGE_API_KEY"):
            raise SystemExit(
                "VOYAGE_API_KEY is not set. This backend calls a paid API and will not guess "
                "at credentials; run it on the host whose environment already has the key."
            )
        self.client = voyageai.Client()
        vectors: list[list[float]] = []
        texts = [window.text for window in windows]
        for start in range(0, len(texts), self.BATCH):
            batch = texts[start : start + self.BATCH]
            vectors.extend(
                self.client.embed(batch, model=model, input_type="document").embeddings
            )
            print(
                f"  embedded {min(start + self.BATCH, len(texts)):>6} / {len(texts)}",
                file=sys.stderr,
            )
        self.matrix = numpy.array(vectors, dtype="float32")
        norms = numpy.linalg.norm(self.matrix, axis=1, keepdims=True)
        self.matrix = self.matrix / numpy.where(norms == 0, 1, norms)

    def scores(self, query: str) -> dict[int, float]:
        vector = self.numpy.array(
            self.client.embed([query], model=self.model, input_type="query").embeddings[0],
            dtype="float32",
        )
        vector = vector / (self.numpy.linalg.norm(vector) or 1)
        return {index: float(value) for index, value in enumerate(self.matrix @ vector)}


def estimate_tokens(texts) -> int:
    """Word count times 1.35, which is the usual English ratio and errs high.

    Erring high is the point: this number gates a paid run, and an estimate that flatters the
    corpus would let a run start that the caller would not have approved.
    """

    return int(sum(len(text.split()) for text in texts) * 1.35)


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

    def ranking(self, query: str) -> list[tuple[str, float]]:
        result = self.adapter.search(
            self.namespace, query, gating=self.gating, limit=self.limit
        )
        if result.abstained:
            # An abstention is a DECISION, not an empty index, and the two must not read alike.
            # A product that declines here has retrieved nothing on purpose and should score as a
            # miss, with the count reported so nobody reads the miss as a ranking failure.
            self.abstentions += 1
        return [(hit.source_path, hit.score) for hit in result.hits]


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
        # An arm ranks whole documents itself, so no windowing happens and none is claimed: the
        # window count below is the corpus's, reported for comparability, not something the arm
        # was scored over.
        windows = []
        documents = set(CorpusManifest.load(corpus_root).sessions)
        backend = arm
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
        competitors = order[: (first - 1)] if first else order[:top]
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
                    Counter(tier_of(rel, plan, plants) for rel in competitors)
                ),
            }
        )
    scored = [row for row in rows if not row["gold_withheld_by_condition"]]

    # Every rate below is over SCORED queries: the ones that have a right answer to find. A task
    # whose governing session the condition withheld is not a miss, it is not a question.
    def hit_at(k: int) -> float:
        return sum(1 for row in scored if row["rank"] and row["rank"] <= k) / max(1, len(scored))

    synthesis = [row for row in scored if row["gold_documents"] > 1]
    plant_ranked = [row for row in rows if row["plant_rank"]]
    summary = {
        "corpus": corpus_root.as_posix(),
        "backend": backend.name,
        "documents": len(documents),
        "windows": len(windows),
        "gating": getattr(backend, "gating", None),
        "abstentions": getattr(backend, "abstentions", None),
        "queries": len(scored),
        "gold_withheld_by_condition": sorted(withheld),
        "plants_ranked_top10": sum(1 for row in plant_ranked if row["plant_rank"] <= 10),
        "plants_present": len(plant_ranked),
        "hit@1": round(hit_at(1), 4),
        "hit@5": round(hit_at(5), 4),
        "hit@10": round(hit_at(10), 4),
        "mrr@10": round(
            sum(1.0 / row["rank"] for row in scored if row["rank"] and row["rank"] <= 10)
            / max(1, len(scored)),
            4,
        ),
        "median_rank": (
            sorted(row["rank"] or 10**9 for row in scored)[len(scored) // 2] if scored else None
        ),
        # Averaged over the queries that RETRIEVED the gold session at all. Folding a miss in as
        # zero competitors was the first version of this line and it reports a corpus as easier
        # the harder it gets, since a total failure would have contributed the smallest possible
        # number to the mean. Misses are counted, not absorbed.
        "mean_competitors_above_gold": (
            round(
                sum(row["competitors_above_gold"] for row in scored if row["rank"])
                / max(1, sum(1 for row in scored if row["rank"])),
                2,
            )
        ),
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
        "competitor_tiers": dict(
            sum((Counter(row["competitor_tiers"]) for row in scored), Counter())
        ),
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
        help="hard ceiling per corpus for the paid voyage backend; it refuses rather than warns",
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
    results = []
    for root in roots:
        if not (root / "manifest.json").is_file():
            raise SystemExit(f"{root} has no manifest.json; it is not a corpus root")
        arm = build_arm(args.arm, root, args.gating, args.namespace, args.top) if args.arm else None
        label = arm.name if arm is not None else f"{args.backend} ({model})"
        print(f"probing {root.as_posix()} with {label} ...", file=sys.stderr)
        results.append(probe(root, args.backend, model, args.top, args.max_tokens, arm))

    header = (
        f"{'documents':>10} {'windows':>9} {'hit@1':>7} {'hit@5':>7} {'hit@10':>7} "
        f"{'mrr@10':>7} {'med rank':>9} {'mean above':>11} {'miss':>5}  corpus"
    )
    print(header)
    for result in results:
        s = result["summary"]
        print(
            f"{s['documents']:>10} {s['windows']:>9} {s['hit@1']:>7.3f} {s['hit@5']:>7.3f} "
            f"{s['hit@10']:>7.3f} {s['mrr@10']:>7.3f} {s['median_rank']:>9} "
            f"{s['mean_competitors_above_gold']:>11.2f} {s['misses']:>5}  {s['corpus']}"
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
                tiers = ", ".join(f"{k}:{v}" for k, v in sorted(row["competitor_tiers"].items()))
                print(f"{row['task_id']:22s} {row['rank']!s:>6} "
                      f"{row['competitors_above_gold']!s:>6}  {tiers}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"\nwrote {out.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
