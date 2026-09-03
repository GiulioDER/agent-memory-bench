# 015: Supermemory VPS2 local ingestion amendment

Status: FROZEN before the amended smoke measurement.

## Reason for amendment

The original Supermemory treatment in `014-supermemory-adapter.md` uses `POST /v3/documents`.
On VPS2, the official Supermemory Local server accepted those writes but its asynchronous memory
agent did not finish within the smoke window. A clean one document check remained `indexing` after
approximately three minutes with the local Ollama model. The same server and plugin were retained.

This is an environment qualification failure, not a product score. The local server exposes a
second documented write surface, `POST /v4/memories`, which accepts explicit memories and makes them
available through the same `/v4/profile` read surface used by the official Claude Code hooks.

## Amended treatment

Only the VPS2 run uses `SUPERMEMORY_BENCHMARK_INGEST_MODE=direct_static_memories`. Each rendered
transcript is split deterministically at 9,000 characters when needed, and each part is written as
one explicit static memory through `POST /v4/memories`. No transcript bytes are rewritten except for
the deterministic split. The official pinned Claude Code plugin and its lifecycle hooks remain the
session integration. The mode, endpoint, part counts, accepted item count, and local model are
published in the run artifacts.

The original `official_documents` mode remains available and unchanged. Any result produced by the
amended mode is labeled as Supermemory Local explicit static memory ingestion and is not pooled with
the failed original mode.

## Prediction and gates

Before the amended smoke measurement, I predict that all corpus parts will be accepted, at least
one part will be returned by `/v4/profile`, both required hooks will pass admission, and the smoke
will project below 18,000 seconds for 24 tasks by 3 seeds. A smoke that does not satisfy every gate
is not promoted to the full benchmark.

The amended smoke uses the same 600 second smoke limit and 18,000 second projected full-run limit
from preregistration 014. The full run must wait for the amended ingestion report and must use the
same pinned plugin, model, task roster, seed roster, and admission rules.

## Source disclosure

The endpoint is part of the official Supermemory API. Supermemory Local remains self-hosted on VPS2
with local embeddings. The explicit static route avoids Supermemory's local memory extraction model,
so extraction is not claimed as part of this amended treatment. That limitation is part of the
publishable method and must appear beside the results.

<!-- results are appended below this line -->
