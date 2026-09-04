"""A small, fixed BM25 over corpus documents. No model, no network, no spend.

This exists so a plant can be checked for FINDABILITY. Every other gate in this repository checks
that a plant is CORRECT: `audit_plants` checks it leaks no true fact, `test_damage_detection`
checks its signature fires on the plant and stays silent on a factless session. None of them
checks that anything RETRIEVES it, and a plant nothing retrieves cannot mislead anybody, so its
condition measures nothing for that task.

⚠️ **Two cheaper proxies were tried first and both failed, which is why this is BM25 and not a
one-liner.** Measured against fifteen plants whose true ranks were known:

    absolute term overlap    ts-tz-utc ranks 4th with overlap 0.061; ts-glob-hidden ranks 45th
                             with 0.571. No threshold separates them.
    ranking by that overlap  65 concordant against 29 discordant pairs. ts-golden-regen, truly
                             61st, came out 13th.

Findability is RELATIVE. A document with modest overlap ranks first when nothing competes and a
document with high overlap ranks 45th when plenty does, so a score that cannot see the rest of the
corpus cannot answer the question. That is what BM25's inverse document frequency supplies.

✅ **It landed, and it now imports this.** `scripts/retrieval_probe.py` carried a second BM25
until 2026-08-30 (finding F-24), differing in `k1`, the tokenizer, the stoplist and whether query
terms were deduplicated; `scripts/audit_findability.py` carried a third copy of the WINDOWING,
with a different stride. All three are gone. What that cost, and what the numbers did, is in
`docs/audit/2026-08-30-audit-fix-record.md`.

⚠️ **Two things measured on the way, both worth knowing before touching the parameters.**

1. **Deduplicating query terms is wrong, and it was costing a lot.** The probe scored
   `set(tokenize(query))`. Textbook BM25 sums over query terms, so a term appearing twice in a
   prompt contributes twice; `set()` silently discards that weight. Measured over 4,900 documents
   and 34 real prompts, removing the dedup moved hit@1 from 0.1471 to 0.2941 and MRR@10 from
   0.2533 to 0.4118. This module never deduplicated, so nothing here changes.
2. **Whether to window DEPENDS ON CORPUS SIZE, and the ordering inverts.** Over the 196-document
   feed, scoring whole documents beats 160-word windows (hit@1 0.6765 against 0.5000). Over the
   4,900-document haystack it reverses (0.2941 windowed against 0.2647 whole). So neither is
   "the right unit", and a call site has to say which question it is asking. `window_words`
   below is therefore explicit and defaults to OFF, matching this module's original behaviour.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

#: Words carrying no discriminating signal in a corpus of software-convention prose. Deliberately
#: short: BM25's IDF already suppresses anything common, so a long list would be doing the same
#: job twice and less well.
STOPWORDS = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "into", "is", "it", "its", "of", "on", "or", "that", "the", "this", "to", "with", "was", "were", "will", "would", "can", "could", "should", "must", "not", "no", "if", "then", "than", "so", "what", "which", "when", "where"]
)

_TOKEN = re.compile(r"[a-z][a-z0-9_]*")

K1 = 1.5
B = 0.75


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens of two characters or more, stopwords removed."""

    return [w for w in _TOKEN.findall(text.lower()) if len(w) > 1 and w not in STOPWORDS]


#: Scoring-window defaults, used only when `window_words` is passed. Overlapping on purpose:
#: at stride == size, a fact that straddles a boundary is split across two windows and scores
#: fully in neither. `scripts/audit_findability.py` used a non-overlapping stride while its
#: comment said it matched the probe's, which used 120; that is the kind of divergence a shared
#: default exists to prevent.
WINDOW_WORDS = 160
WINDOW_STRIDE = 120


def windows_of(text: str, size: int, stride: int) -> list[str]:
    """Overlapping word windows over the RAW text, before tokenizing.

    Raw rather than tokenized, because a window is meant to be a span of the document as written.
    Windowing the token stream (stopwords already dropped) makes a "160-word window" cover a
    different and variable amount of source text per document, so two documents' windows are not
    comparable and neither are two implementations'.
    """

    words = text.split()
    if not words:
        return [""]
    out = []
    for start in range(0, len(words), stride):
        out.append(" ".join(words[start : start + size]))
        if start + size >= len(words):
            break
    return out


class Bm25Index:
    """A fixed BM25 index over a set of named documents.

    Fixed on purpose: `K1` and `B` are the textbook defaults and are not tuned. A gate whose
    threshold moves with its own parameters measures the parameters. That principle is why the
    parameters here were NOT changed to the ones that maximise hit@1 when the two implementations
    were merged: a reference ranker tuned against this corpus would flatter or punish the arms
    measured against it, and the number would mean less for looking better.

    Pass `window_words` to score overlapping windows instead of whole documents, taking each
    document's best window. `ranking`, `score` and `rank_of` all speak DOCUMENT names either way,
    so a caller cannot accidentally publish a window id as a document rank.
    """

    def __init__(
        self,
        documents: Mapping[str, str],
        *,
        window_words: int | None = None,
        window_stride: int | None = None,
    ) -> None:
        self.names: list[str] = list(documents)
        self.window_words = window_words
        self.window_stride = window_stride or WINDOW_STRIDE
        #: unit key -> owning document name. Identity when not windowing.
        self._owner: dict[str, str] = {}
        units: dict[str, str] = {}
        for name, text in documents.items():
            if window_words is None:
                units[name] = text
                self._owner[name] = name
                continue
            for index, chunk in enumerate(
                windows_of(text, window_words, self.window_stride)
            ):
                key = f"{name}#{index}"
                units[key] = chunk
                self._owner[key] = name
        self._tokens: dict[str, Counter[str]] = {
            key: Counter(tokenize(text)) for key, text in units.items()
        }
        self._lengths = {key: sum(counts.values()) for key, counts in self._tokens.items()}
        self._avg = (sum(self._lengths.values()) / len(self._lengths)) if self._lengths else 0.0
        containing: Counter[str] = Counter()
        for counts in self._tokens.values():
            containing.update(counts.keys())
        n = len(self._tokens)
        self._idf = {
            term: math.log(1.0 + (n - df + 0.5) / (df + 0.5)) for term, df in containing.items()
        }

    def _unit_score(self, query: str, key: str) -> float:
        counts = self._tokens.get(key)
        if not counts:
            return 0.0
        length = self._lengths[key] or 1
        total = 0.0
        # NOT `set(...)`. A term appearing twice in a prompt contributes twice, which is what
        # BM25's query-term-frequency weighting means. See point 1 of the module docstring.
        for term in tokenize(query):
            freq = counts.get(term, 0)
            if not freq:
                continue
            denominator = freq + K1 * (1.0 - B + B * length / (self._avg or 1.0))
            total += self._idf.get(term, 0.0) * freq * (K1 + 1.0) / denominator
        return total

    def score(self, query: str, name: str) -> float:
        """A DOCUMENT's score: its best window's when windowing, its own otherwise."""

        if self.window_words is None:
            return self._unit_score(query, name)
        best = 0.0
        for key, owner in self._owner.items():
            if owner != name:
                continue
            best = max(best, self._unit_score(query, key))
        return best

    def ranking(self, query: str) -> list[tuple[str, float]]:
        """Every DOCUMENT, best first. Ties broken by name so a rank is reproducible.

        Documents even when windowing: a window id leaking out of here would be read downstream
        as a document rank, which is the same class of error as F-08, where chunk-level hits were
        counted as documents and inflated an arm's apparent coverage.
        """

        best: dict[str, float] = dict.fromkeys(self.names, 0.0)
        for key, owner in self._owner.items():
            value = self._unit_score(query, key)
            best[owner] = max(best[owner], value)
        return sorted(best.items(), key=lambda pair: (-pair[1], pair[0]))

    def rank_of(self, query: str, names: Iterable[str]) -> int | None:
        """The best (lowest) 1-based rank achieved by any of `names`, or None if absent."""

        wanted = set(names)
        if not wanted:
            return None
        for position, (name, _score) in enumerate(self.ranking(query), start=1):
            if name in wanted:
                return position
        return None


def read_corpus(root: str | Path, pattern: str = "**/*.jsonl") -> dict[str, str]:
    """Every document under `root`, keyed by its path relative to `root`.

    Read as raw text rather than parsed: a session's tool calls, file contents and prose all carry
    retrievable signal, and which JSON field they arrived in is not what a ranker sees.
    """

    root = Path(root)
    documents: dict[str, str] = {}
    for path in sorted(root.glob(pattern)):
        if path.is_file():
            documents[path.relative_to(root).as_posix()] = path.read_text(
                encoding="utf-8", errors="replace"
            )
    return documents


def findability(
    root: str | Path, query: str, names: Sequence[str]
) -> tuple[int | None, int]:
    """`(best rank of any of `names`, corpus size)` for `query`."""

    documents = read_corpus(root)
    index = Bm25Index(documents)
    return index.rank_of(query, names), len(documents)
