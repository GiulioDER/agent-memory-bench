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


def render_corpus(session_paths: list[Path], target_dir: Path) -> int:
    """Render a set of transcripts into ``target_dir``; returns the count written."""

    target_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for source in sorted(session_paths):
        out = target_dir / source.with_suffix(".md").name
        out.write_text(render_transcript(source), encoding="utf-8")
        written += 1
    return written
