"""RE-call graph retrieval arm without the Voyage reranker."""

from __future__ import annotations

from pathlib import Path

from adapters.recall.adapter import RecallAdapter


class RecallGraphFullToolsAdapter(RecallAdapter):
    """The Context4 graph path with no reranker and the full frozen MCP surface."""

    name = "recall_graph_fulltools"
    config_path = Path(__file__).with_name("config.frozen.json")


__all__ = ["RecallGraphFullToolsAdapter"]

