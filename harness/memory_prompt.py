"""The one deterministic memory wrapper shared by oracle and prefetch arms.

The field labels are deliberately generic. They used to read ``Status:`` and ``Supersedes:``, which
are RE-call's own verdict vocabulary, and `oracle_memory` is the CEILING every product is measured
against: a ceiling written in one vendor's idiom invites the reading that the ceiling was drawn
around that vendor's output shape. It was not (the bundle is the corpus's own authored decision
turn, supplied with no retrieval at all, and no competitor is disadvantaged by it), which is exactly
why the labels should not suggest otherwise.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from .corpus_names import NEUTRAL_NAME, neutral_stem
from .memory_bundles import MemoryItem


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimated_input_tokens(text: str) -> int:
    return len(text.split())


def shown_source(source: str) -> str:
    """The source identifier an agent may read: always a neutral name.

    Until 2026-09-26 this printed the raw ``source_path``, which for `oracle_memory` is a corpus
    path (``sessions/ts-x/p01.jsonl``, naming the task) and for `recall_prefetch` is whatever name
    recall returned, which was ``sessions__ts-x__stale_y.md`` and named the plant's role. A name
    that is already neutral passes through; anything else is replaced by the neutral name of
    that string, which is still stable per document and says nothing about it.
    """

    tail = source.replace("\\", "/").rsplit("/", 1)[-1]
    if NEUTRAL_NAME.match(tail):
        return tail
    return neutral_stem(source) + ".md"


def format_memory_items(items: Iterable[MemoryItem]) -> str:
    ordered = sorted(items, key=lambda item: item.memory_id)
    if not ordered:
        return "Project memory:\n\n"
    blocks = ["Project memory:", ""]
    for item in ordered:
        blocks.extend(
            [
                "[Evidence item]",
                item.evidence_text,
                "",
                f"Recorded: {item.recorded_at}",
                f"Currency: {item.validity}",
                f"Source: {shown_source(item.source_path)}",
            ]
        )
        if item.supersedes:
            replaced = ", ".join(
                shown_source(part.strip()) for part in str(item.supersedes).split(",") if part.strip()
            )
            blocks.append(f"Replaces: {replaced}")
        blocks.extend(["[/Evidence item]", ""])
    return "\n".join(blocks).rstrip() + "\n"
