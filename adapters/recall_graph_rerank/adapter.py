"""The graph plus Voyage reranker AMB arm.

This arm changes two deliberately declared product settings from the Context4 baseline: the
rendered corpus carries explicit session-order graph relations, and the MCP server enables Voyage
rerank-2.5.  The adapter still enters through RE-call's official MCP server and uses the same
prompt and model as the baseline.
"""

from __future__ import annotations

from pathlib import Path

from adapters.recall_rerank.adapter import RecallRerankAdapter


class RecallGraphRerankAdapter(RecallRerankAdapter):
    name = "recall_graph_rerank"
    config_path = Path(__file__).with_name("config.frozen.json")


__all__ = ["RecallGraphRerankAdapter"]
