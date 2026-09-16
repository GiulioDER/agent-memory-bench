"""RE-call graph retrieval arm without the Voyage reranker."""

from __future__ import annotations

from pathlib import Path

from adapters.recall.adapter import RecallAdapter


class RecallGraphFullToolsAdapter(RecallAdapter):
    """The Context4 graph path with no reranker and the full frozen MCP surface."""

    name = "recall_graph_fulltools"
    config_path = Path(__file__).with_name("config.frozen.json")


class RecallGraphFullToolsProtocolAdapter(RecallGraphFullToolsAdapter):
    """Official-014's contemporaneous protocol control."""

    name = "recall_graph_fulltools_protocol"


class RecallGraphFullToolsQualityGateAdapter(RecallGraphFullToolsAdapter):
    """Official-014's protocol plus the frozen quality gate."""

    name = "recall_graph_fulltools_quality_gate"


class RecallGraphFullToolsDecisionProtocolAdapter(RecallGraphFullToolsAdapter):
    """Official-015's frozen compact search-first decision protocol."""

    name = "recall_graph_fulltools_decision_protocol"


__all__ = [
    "RecallGraphFullToolsAdapter",
    "RecallGraphFullToolsDecisionProtocolAdapter",
    "RecallGraphFullToolsProtocolAdapter",
    "RecallGraphFullToolsQualityGateAdapter",
]
