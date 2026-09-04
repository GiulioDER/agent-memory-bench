"""The ``recall_rerank`` arm: the same recall, with the Voyage reranker turned on.

One arm, one difference. `recall` and `recall_rerank` serve the same tenant from the same
generation, with the same embedder, the same trust gate, the same eight tools and a byte-identical
instruction; the only thing that differs is that this arm's server reranks its candidate pool with
Voyage's cross-encoder before returning it. That is what makes the contrast attributable: the two
arms run as a PAIR inside one grid, so the corpus feed, the model, the task suite and the admitted
set are held constant by construction rather than by an argument about comparability across runs.

⚠️ **This is not a free setting, and 0.11.0 gives no way to make it one.** `recall_mcp.factories`
builds ``FallbackReranker(primary=Voyage, fallback=CrossEncoderReranker(local))`` EAGERLY when the
model name is a Voyage one, so selecting Voyage installs and loads a local cross-encoder too. That
is why this arm's pin carries the ``rerank`` extra while `recall`'s does not, and why it needs its
own interpreter: adding torch and transformers to the venv `recall` runs would change the artifact
every published run was measured on, for an arm that does not use them.

Everything else is inherited. The subclass repoints one path and adds no behaviour, which is the
property that lets a reader check the whole difference between the two arms by diffing two frozen
config files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.recall.adapter import RecallAdapter
from harness.adapters.base import RankedResult

_CONFIG_PATH = Path(__file__).with_name("config.frozen.json")


class RecallRerankAdapter(RecallAdapter):
    """recall, reranked. See `config.frozen.json` for the whole of the difference."""

    name = "recall_rerank"
    config_path = _CONFIG_PATH

    def search(self, *args: Any, **kwargs: Any) -> RankedResult:
        """Refused, because THIS path does not rerank and would not say so.

        ⛔ The reranker exists only in `recall_mcp`. `recall.cli`, which `RecallAdapter.search`
        shells out to, contains no reference to `RECALL_RERANK` and builds no reranker: verified
        2026-09-02 against the installed 0.11.0 by grepping both packages. The environment this
        adapter hands that subprocess carries `RECALL_RERANK=1` and the CLI ignores it.

        So inheriting `search` would return the BASE arm's ranking under this arm's name, from a
        command whose environment says otherwise, with nothing raising. `scripts/retrieval_probe.py
        --arm recall_rerank` would then report the two arms as identical and that number would be
        an artefact of the probe rather than a property of the reranker. A visible refusal is the
        better failure, by the same argument `parse_ranked_search` makes about never turning a
        parse failure into an empty result.

        The agent's path is unaffected: sessions reach recall through the MCP server, which does
        rerank, and `_remote_command` is what carries the setting there.
        """

        raise NotImplementedError(
            "recall_rerank has no CLI search path: recall's reranker lives in recall_mcp, and "
            "`recall.cli` ignores RECALL_RERANK, so this would publish the unreranked ranking "
            "under this arm's name. Measure this arm's retrieval through its MCP server, or probe "
            "`recall` if the unreranked ranking is what you want."
        )
