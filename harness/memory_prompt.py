"""The one deterministic memory wrapper shared by oracle and prefetch arms."""

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
                f"Status: {item.validity}",
                f"Source: {item.source_path}",
            ]
        )
        if item.supersedes:
            blocks.append(f"Supersedes: {item.supersedes}")
        blocks.extend(["[/Evidence item]", ""])
    return "\n".join(blocks).rstrip() + "\n"
