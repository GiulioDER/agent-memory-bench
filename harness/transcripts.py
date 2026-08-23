"""Rendering the corpus's JSONL session transcripts into readable markdown.

Lives in the harness, not in any adapter, because more than one arm consumes it (fs_grep
serves the render directly; file-ingesting products index it) and the render must be
byte-identical wherever it is used: a feed that differs between arms is not a shared feed.
"""

from __future__ import annotations

import json
from pathlib import Path


def render_transcript(jsonl_path: Path) -> str:
    """Render one session transcript JSONL into greppable markdown, verbatim content."""

    lines = [f"# Session notes: {jsonl_path.stem}", ""]
    for raw in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        event = json.loads(raw)
        role = event.get("role", "?")
        content = event.get("content", "")
        tool = event.get("tool_name")
        if tool:
            lines.append(f"**{role} [{tool}]**: {content}")
            result = event.get("tool_result")
            if result:
                lines.append(f"> {result}")
        else:
            lines.append(f"**{role}**: {content}")
        lines.append("")
    return "\n".join(lines)


def render_corpus(
    session_paths: list[Path], target_dir: Path, *, root: Path | None = None
) -> int:
    """Render transcripts into ``target_dir``; returns the count written.

    With ``root`` given, each output is named from its path relative to ``root`` with
    separators flattened to ``__`` (``sessions/ts-dedup-order/p01.jsonl`` becomes
    ``sessions__ts-dedup-order__p01.md``): unique by construction AND self-identifying in a
    retrieval result. Without ``root``, bare filenames are used and a collision RAISES,
    because the first version of this function silently overwrote colliding names and
    shipped a corpus holding one precursor out of twenty-four.
    """

    target_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    seen: dict[str, Path] = {}
    for source in sorted(session_paths):
        if root is not None:
            name = source.relative_to(root).with_suffix(".md").as_posix().replace("/", "__")
        else:
            name = source.with_suffix(".md").name
        if name in seen:
            raise ValueError(
                f"transcript name collision: {source} and {seen[name]} both render to "
                f"{name!r}; pass root= so names mirror their paths"
            )
        seen[name] = source
        (target_dir / name).write_text(render_transcript(source), encoding="utf-8")
        written += 1
    return written
