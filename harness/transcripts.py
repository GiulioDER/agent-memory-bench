"""Rendering the corpus's JSONL session transcripts into readable markdown.

Lives in the harness, not in any adapter, because more than one arm consumes it (fs_grep
serves the render directly; file-ingesting products index it) and the render must be
byte-identical wherever it is used: a feed that differs between arms is not a shared feed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from harness.corpus_names import neutral_key_map, rendered_name
from harness.lineage import render_frontmatter

__all__ = ["neutral_key_map", "render_corpus", "render_transcript", "rendered_name"]


def render_transcript(
    jsonl_path: Path, frontmatter: Mapping[str, str] | None = None
) -> str:
    """Render one session transcript JSONL into greppable markdown, verbatim content.

    ``frontmatter`` prepends a YAML block declaring validity and supersession, which is the only
    place recall can learn that one document replaces another; see `harness/lineage.py`.

    It defaults to None, producing output byte-identical to before preregistration 023. That is
    deliberate: the control tier then needs no separate code path and cannot drift away from the
    thing it is controlling for.
    """

    lines: list[str] = []
    block = render_frontmatter(frontmatter)
    if block:
        lines.append(block)
    # No stem in the heading: for a planted session it was the plant's own name
    # (`stale_numeric_switch`), which sits in the first chunk and reached the agent.
    lines.extend(["# Session notes", ""])
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
    session_paths: list[Path],
    target_dir: Path,
    *,
    root: Path | None = None,
    lineage: Mapping[Path, Mapping[str, str]] | None = None,
    graph: Mapping[Path, Mapping[str, str]] | None = None,
) -> int:
    """Render transcripts into ``target_dir``; returns the count written.

    Each output is named by :func:`rendered_name`, a neutral ``notes__<digest>.md`` derived from
    its path relative to ``root`` (or from its bare filename without ``root``). The name used to
    mirror the path, ``sessions__ts-dedup-order__p01.md``, which made it self-identifying in a
    retrieval result; that was the defect, not a feature. Join a returned name back to the corpus
    with :func:`neutral_key_map`. A collision still RAISES, because the first version of this
    function silently overwrote colliding names and shipped a corpus holding one precursor out of
    twenty-four.

    ``lineage`` maps a session path to the frontmatter it should carry, as built by
    `harness.lineage.frontmatter_for`. The pairing logic lives there rather than here: this
    function decides NAMES, and a renderer that also decided which document supersedes which would
    be two responsibilities in one place, neither testable alone.

    Omitted, every render is byte-identical to before preregistration 023, so the control tier is
    the same code path as production rather than a reconstruction of it.
    """

    target_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    seen: dict[str, Path] = {}
    for source in sorted(session_paths):
        name = rendered_name(source, root)
        if name in seen:
            raise ValueError(
                f"transcript name collision: {source} and {seen[name]} both render to "
                f"{name!r}; pass root= so names derive from full corpus paths"
            )
        seen[name] = source
        meta = {
            **(lineage or {}).get(source, {}),
            **(graph or {}).get(source, {}),
        }
        (target_dir / name).write_text(
            render_transcript(source, meta or None), encoding="utf-8"
        )
        written += 1
    return written
