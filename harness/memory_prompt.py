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

from .memory_bundles import MemoryItem


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimated_input_tokens(text: str) -> int:
    return len(text.split())


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
                f"Source: {item.source_path}",
            ]
        )
        if item.supersedes:
            blocks.append(f"Replaces: {item.supersedes}")
        blocks.extend(["[/Evidence item]", ""])
    return "\n".join(blocks).rstrip() + "\n"
