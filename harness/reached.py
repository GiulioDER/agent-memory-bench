"""Did the governing memory actually reach the agent? Measured by CONTENT, not by filename.

## The metric this replaces, and why it could not survive a competitor

`scripts/analyze_pilot.py` asked whether the string ``sessions__<task_id>__`` appeared anywhere in
a session's retrieved contexts. That string is the name `harness/transcripts.py` gives a rendered
corpus file, and recall returns it verbatim in every hit as ``"source"``. So the metric measured
"the product returned a result carrying our source filename".

Three things follow, and the third is the one that matters:

1. A product that returns extracted facts rather than source documents scores **zero with perfect
   retrieval**. mem0 returns memories. Zep returns graph nodes. Neither has a reason to echo a
   filename from a corpus it ingested weeks earlier.
2. It quietly rewards surfacing provenance strings, which is an integration shape rather than a
   retrieval quality.
3. It is not only a reporting number. Preregistration 002's frozen eligibility rule is
   "reached-given-searched at least 0.50", and a model, or an arm, that fails it does not enter the
   comparison. Applied unchanged to an extraction product, that rule disqualifies it for a reason
   that has nothing to do with whether it found the right memory.

So the question is asked of the TEXT: does what came back state the governing fact? The task's own
``fact_terms`` already carry that, they are audited for presence in the task's own sessions and for
absence everywhere else (`scripts/audit_corpus.py`), and they are compared through
`harness.plants.normalise` so markdown emphasis and hyphenation cannot hide a match.

The old path-based signal is kept as a SEPARATE field rather than deleted. It is what the published
runs measured, so a re-analysis has to be able to reproduce them, and the gap between the two is
itself the finding: an arm where ``reached_by_path`` and ``reached_by_content`` disagree is an arm
whose integration shape was doing the work.

## Three signals, and they BRACKET the truth rather than one being correct

Re-scoring the published runs through all three, over the recall arm's searching sessions:

    signal                              pilot-003-deepseek   pilot-004-placebo
    reached_by_path      (published)          0.850                0.926
    reached_by_content   (primary)            0.550                0.648
    reached_by_evidence  (strict)             0.333                0.444

They differ because they ask different questions of the same bytes, and the ordering is not an
accident:

- ``reached_by_path`` is a LOOSE UPPER BOUND. recall returns chunks of a rendered session, so a
  chunk can carry the right filename while containing a part of the conversation that never states
  the decision. "The right document was touched" is not "the deciding sentence arrived".
- ``reached_by_evidence`` is a STRICT LOWER BOUND. It looks for word overlap with the authored
  closing turn alone, and a chunk covering the ANALYSIS that led to the decision states the fact
  perfectly well while sharing none of the closing turn's phrasing.
- ``reached_by_content`` sits between them and is the primary, because the ``fact_terms`` it matches
  are the audited statement of the governing fact: present in the task's own sessions, absent from
  every other document, checked by `scripts/audit_corpus.py` on every run.

⚠️ **The published mechanism figures used the loosest of the three.** A reader of "reached-given-
searched 0.85" reasonably hears "the governing memo reached the agent in 85% of searching
sessions"; the defensible range is 0.33 to 0.85 with 0.55 as the point estimate. This matters
beyond presentation: preregistration 002's frozen eligibility rule is "reached-given-searched at
least 0.50", and deepseek clears it on two of the three signals and fails it on the third. Any
re-use of that rule has to say which signal it means.

None of the three is a semantic match, so all three under-count a paraphrase. Report the bracket.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .plants import normalise
from .schema import SessionRecord

#: How many of a task's fact terms must appear in the retrieved text before the governing memory
#: counts as having reached the agent. One is enough: the terms are audited to be unique to this
#: task, so a single hit is already evidence the right document came back.
MIN_TERMS = 1


def retrieved_text(record: SessionRecord, *, tool_prefix: str = "mcp__") -> str:
    """Everything a memory layer put in front of the model this session, normalised.

    Reads BOTH ``retrieved_contexts`` and the raw outputs of memory tool calls, because an adapter
    that does not populate the first still leaves the second, and a metric that saw only one of
    them would score an arm on its bookkeeping rather than on its retrieval.
    """

    parts: list[str] = list(record.retrieved_contexts)
    for call in record.tool_calls:
        if str(call.get("name", "")).startswith(tool_prefix):
            output = call.get("output")
            if isinstance(output, str) and output:
                parts.append(output)
    # Injected arms (oracle_memory, recall_prefetch) never make a tool call: their memory arrives in
    # the system prompt, and the adapter records it here.
    injected = record.metadata.get("injected_memory_text")
    if isinstance(injected, str) and injected:
        parts.append(injected)
    return normalise(" ".join(parts))


def reached_by_content(
    record: SessionRecord, fact_terms: Sequence[str], *, tool_prefix: str = "mcp__"
) -> tuple[bool, list[str]]:
    """Whether the retrieved text states this task's governing fact, and which terms matched."""

    if not fact_terms:
        return False, []
    haystack = retrieved_text(record, tool_prefix=tool_prefix)
    matched = [term for term in fact_terms if normalise(term) in haystack]
    return len(matched) >= MIN_TERMS, matched


#: Word count of the overlapping run required by :func:`reached_by_evidence`. Stable across 6, 8
#: and 12 on every published run, so the choice is not load-bearing.
SHINGLE = 8


def _shingles(text: str, size: int = SHINGLE) -> set[str]:
    words = normalise(text).split()
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def reached_by_evidence(
    record: SessionRecord, evidence_text: str, *, tool_prefix: str = "mcp__"
) -> bool:
    """Strict lower bound: did the retrieved text overlap the authored decision turn itself.

    ``evidence_text`` is the task's oracle bundle item, which `scripts/build_oracle_bundles.py`
    takes as the precursor's closing user turn: the sentence in which the decision is actually
    stated. Overlap is an 8-word run, which is long enough that it cannot fire on shared English
    and short enough to survive a chunk boundary landing mid-sentence.

    It is a LOWER bound because a retrieved chunk covering the analysis that led to the decision
    conveys the fact while sharing none of this turn's wording.
    """

    if not evidence_text:
        return False
    return bool(
        _shingles(evidence_text) & _shingles(retrieved_text(record, tool_prefix=tool_prefix))
    )


def reached_by_path(record: SessionRecord, *, tool_prefix: str = "mcp__") -> bool:
    """The legacy signal: did a result carry this corpus's own source filename.

    Kept so the published runs can be reproduced exactly, and so the disagreement with
    :func:`reached_by_content` can be published as its own number.
    """

    marker = f"sessions__{record.task_id}__"
    if any(marker in context for context in record.retrieved_contexts):
        return True
    return any(
        marker in str(call.get("output", ""))
        for call in record.tool_calls
        if str(call.get("name", "")).startswith(tool_prefix)
    )


def mechanism(
    records: Iterable[SessionRecord],
    fact_terms_by_task: Mapping[str, Sequence[str]],
    *,
    evidence_by_task: Mapping[str, str] | None = None,
    tool_prefix: str = "mcp__",
) -> dict[str, Any]:
    """Search rate and all three reached rates for one arm's sessions.

    All three are reported, always. Publishing only the content one would hide that the published
    runs were scored the other way; publishing only the path one is the defect this module exists to
    fix; publishing only the evidence one would understate every arm. The bracket is the answer.
    """

    sessions = list(records)
    if not sessions:
        return {"sessions": 0}
    evidence = evidence_by_task or {}
    searched = [r for r in sessions if r.memory_call_count > 0 or r.retrieved_contexts]
    content = {
        r.cell
        for r in searched
        if reached_by_content(r, fact_terms_by_task.get(r.task_id, ()), tool_prefix=tool_prefix)[0]
    }
    path = {r.cell for r in searched if reached_by_path(r, tool_prefix=tool_prefix)}
    strict = {
        r.cell
        for r in searched
        if reached_by_evidence(r, evidence.get(r.task_id, ""), tool_prefix=tool_prefix)
    }

    def rate(hits: set[tuple[str, int]], denominator: int) -> float | None:
        return round(len(hits) / denominator, 3) if denominator else None

    return {
        "sessions": len(sessions),
        "searched": len(searched),
        "search_rate": rate({r.cell for r in searched}, len(sessions)),
        # The primary, and the one an eligibility rule should name.
        "reached_given_searched": rate(content, len(searched)),
        "reached_overall": rate(content, len(sessions)),
        # The bracket. Loose upper, strict lower. See the module docstring.
        "reached_given_searched_by_path": rate(path, len(searched)),
        "reached_given_searched_by_evidence": rate(strict, len(searched)),
        "reached_counts": {
            "by_content": len(content),
            "by_path": len(path),
            "by_evidence": len(strict),
        },
        # An arm where path and content disagree is an arm whose integration SHAPE moved the
        # metric. Published so a competitor does not have to derive it.
        "path_content_disagreements": len(content ^ path),
        "primary": "reached_by_content",
        "note": (
            "three signals bracket the same question; the published runs used "
            "reached_given_searched_by_path, which is the loosest of the three"
        ),
    }
