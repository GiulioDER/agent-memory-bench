from __future__ import annotations

import json
from pathlib import Path

from harness.graph_metadata import GRAPH_METADATA_MODE, structural_graph_metadata
from harness.transcripts import render_corpus


def test_structural_graph_metadata_links_only_adjacent_sessions(tmp_path: Path) -> None:
    """The graph feed must contain explicit source-backed edges, not prose-based guesses.

    The failure mode is a renderer that accepts the graph mode but drops metadata before writing
    the Markdown feed.  A mutation removing ``graph=`` from ``render_corpus`` must fail at the
    ``recall_graph`` assertion below, which is the real ingest boundary rather than a helper-only
    assertion.
    """
    root = tmp_path / "source"
    task = root / "sessions" / "task-a"
    task.mkdir(parents=True)
    paths = []
    for name in ("p01.jsonl", "p02.jsonl", "p03.jsonl"):
        path = task / name
        path.write_text(json.dumps({"role": "user", "content": name}) + "\n", encoding="utf-8")
        paths.append(path)

    graph = structural_graph_metadata(paths, root)
    assert set(graph) == set(paths)
    assert len(json.loads(graph[paths[0]]["recall_graph"])["relations"]) == 1

    rendered = tmp_path / "rendered"
    render_corpus(paths, rendered, root=root, graph=graph)
    text = (rendered / "sessions__task-a__p01.md").read_text(encoding="utf-8")
    assert "recall_graph:" in text
    assert "sessions__task-a__p02.md" in text
    assert "sessions__task-a__p03.md" not in text


def test_graph_mode_is_explicit() -> None:
    assert GRAPH_METADATA_MODE == "structural_session_order"
