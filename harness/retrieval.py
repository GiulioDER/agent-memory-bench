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

⚠️ A retrieval probe with its own BM25 exists on another branch and is not on master. When it
lands, it should import THIS rather than keep a second copy: two implementations of one ranker is
the defect that produced two different answers to "what is the CI" in `harness/stats.py`, one
function apart, and it took a dedicated test to stop it recurring.
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


class Bm25Index:
    """A fixed BM25 index over a set of named documents.

    Fixed on purpose: `K1` and `B` are the textbook defaults and are not tuned. A gate whose
    threshold moves with its own parameters measures the parameters.
    """

    def __init__(self, documents: Mapping[str, str]) -> None:
        self.names: list[str] = list(documents)
        self._tokens: dict[str, Counter[str]] = {
            name: Counter(tokenize(text)) for name, text in documents.items()
        }
        self._lengths = {name: sum(counts.values()) for name, counts in self._tokens.items()}
        self._avg = (sum(self._lengths.values()) / len(self._lengths)) if self._lengths else 0.0
        containing: Counter[str] = Counter()
        for counts in self._tokens.values():
            containing.update(counts.keys())
        n = len(self._tokens)
        self._idf = {
            term: math.log(1.0 + (n - df + 0.5) / (df + 0.5)) for term, df in containing.items()
        }

    def score(self, query: str, name: str) -> float:
        counts = self._tokens.get(name)
        if not counts:
            return 0.0
        length = self._lengths[name] or 1
        total = 0.0
        for term in tokenize(query):
            freq = counts.get(term, 0)
            if not freq:
                continue
            denominator = freq + K1 * (1.0 - B + B * length / (self._avg or 1.0))
            total += self._idf.get(term, 0.0) * freq * (K1 + 1.0) / denominator
        return total

    def ranking(self, query: str) -> list[tuple[str, float]]:
        """Every document, best first. Ties broken by name so a rank is reproducible."""

        scored = [(name, self.score(query, name)) for name in self.names]
        return sorted(scored, key=lambda pair: (-pair[1], pair[0]))

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
