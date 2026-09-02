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

from adapters.recall.adapter import RecallAdapter

_CONFIG_PATH = Path(__file__).with_name("config.frozen.json")


class RecallRerankAdapter(RecallAdapter):
    """recall, reranked. See `config.frozen.json` for the whole of the difference."""

    name = "recall_rerank"
    config_path = _CONFIG_PATH
