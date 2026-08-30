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

from harness.adapters.base import CorpusManifest
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


def rank_documents(backend, windows: list[Window], query: str) -> list[tuple[str, float]]:
    """Score windows, keep each document's best window, and rank documents by it."""

    best: dict[str, float] = {}
    for index, score in backend.scores(query).items():
        doc = windows[index].doc
        if score > best.get(doc, float("-inf")):
            best[doc] = score
    return sorted(best.items(), key=lambda item: (-item[1], item[0]))


def tier_of(rel: str, plan: dict | None) -> str:
    # `sessions/smoke/` belongs to no task and is gold for nothing, so counting it as signal
    # would report another task's precursor and a bring-up transcript as the same kind of
    # competitor. `scripts/audit_corpus.py` was fixed for exactly this directory once already.
    if rel.startswith("sessions/smoke/"):
        return "smoke"
    if rel.startswith("sessions/"):
        return "other-task-signal"
    if rel.startswith("distractors/"):
        return "real-distractor"
    if plan is not None:
        entry = plan.get("sessions", {}).get(rel)
        if entry:
            return str(entry["tier"])
    return "unknown"


def probe(
    corpus_root: Path, backend_name: str, model: str, top: int, max_tokens: int = 0
) -> dict:
    windows = load_windows(corpus_root)
    plan_path = corpus_root / "haystack.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else None
    if backend_name == "bm25":
        backend = BM25(windows)
    elif backend_name == "voyage":
        backend = Voyage(windows, model, max_tokens)
    else:
        backend = Dense(windows, model)
    documents = {window.doc for window in windows}

    rows = []
    for task in sorted(discover_tasks(), key=lambda t: t.task_id):
        gold = {rel for rel in documents if rel.startswith(f"sessions/{task.task_id}/")}
        if not gold:
            continue
        ranking = rank_documents(backend, windows, task.prompt)
        order = [rel for rel, _ in ranking]
        positions = [index + 1 for index, rel in enumerate(order) if rel in gold]
        first = min(positions) if positions else None
        competitors = order[: (first - 1)] if first else order[:top]
        rows.append(
            {
                "task_id": task.task_id,
                "gold_documents": len(gold),
                "rank": first,
                "all_shards_rank": max(positions) if len(positions) == len(gold) else None,
                "competitors_above_gold": (first - 1) if first else None,
                "competitor_tiers": dict(Counter(tier_of(rel, plan) for rel in competitors)),
            }
        )

    def hit_at(k: int) -> float:
        return sum(1 for row in rows if row["rank"] and row["rank"] <= k) / max(1, len(rows))

    synthesis = [row for row in rows if row["gold_documents"] > 1]
    summary = {
        "corpus": corpus_root.as_posix(),
        "backend": backend.name,
        "documents": len(documents),
        "windows": len(windows),
        "queries": len(rows),
        "hit@1": round(hit_at(1), 4),
        "hit@5": round(hit_at(5), 4),
        "hit@10": round(hit_at(10), 4),
        "mrr@10": round(
            sum(1.0 / row["rank"] for row in rows if row["rank"] and row["rank"] <= 10)
            / max(1, len(rows)),
            4,
        ),
        "median_rank": sorted(row["rank"] or 10**9 for row in rows)[len(rows) // 2] if rows else None,
        # Averaged over the queries that RETRIEVED the gold session at all. Folding a miss in as
        # zero competitors was the first version of this line and it reports a corpus as easier
        # the harder it gets, since a total failure would have contributed the smallest possible
        # number to the mean. Misses are counted, not absorbed.
        "mean_competitors_above_gold": (
            round(
                sum(row["competitors_above_gold"] for row in rows if row["rank"])
                / max(1, sum(1 for row in rows if row["rank"])),
                2,
            )
        ),
        "misses": sum(1 for row in rows if not row["rank"]),
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
            sum((Counter(row["competitor_tiers"]) for row in rows), Counter())
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

    roots = [Path(root) for root in (args.corpus or ["corpus"])]
    model = args.model or (
        "voyage-4" if args.backend == "voyage" else "BAAI/bge-small-en-v1.5"
    )
    results = []
    for root in roots:
        if not (root / "manifest.json").is_file():
            raise SystemExit(f"{root} has no manifest.json; it is not a corpus root")
        print(f"probing {root.as_posix()} with {args.backend} ({model}) ...", file=sys.stderr)
        results.append(probe(root, args.backend, model, args.top, args.max_tokens))

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
