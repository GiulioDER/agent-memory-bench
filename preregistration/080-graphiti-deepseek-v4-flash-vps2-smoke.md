---
name: graphiti-deepseek-v4-flash-vps2-smoke
description: "Bring up Graphiti on VPS2 and verify its real MCP write, visibility, and search path"
valid_from: 2026-09-10
metadata:
  node_type: preregistration
  type: integration-smoke
  model: deepseek/deepseek-v4-flash
  host: vps2
  modified: 2026-09-10T00:00:00Z
---

# Question

Does the pinned official Graphiti MCP server run on VPS2 and complete a real memory write and
search using DeepSeek V4 Flash as the LLM model?

# Prediction

The setup will pass, the MCP server will answer `initialize` and `tools/list`, `get_status` will
report a usable graph database, `add_memory` will accept one deterministic episode, `get_episodes`
will expose it after the asynchronous write completes, and a search over the stored marker will
return the episode or an entity or fact derived from it. The smoke will fail if any of those
boundaries fails, even if the process starts.

# Fixed configuration

* Host: VPS2, Linux, with all Graphiti files and runtime state on VPS2.
* Upstream: `getzep/graphiti`, pinned to commit
  `4bd728790e836950c3922e84f6f989f1380f54f2`.
* MCP transport: official `mcp_server/main.py` over stdio.
* Graph database: disposable Neo4j 5.26 service on VPS2, or the existing VPS2 Graphiti database
  if the operator has already provisioned one for this smoke.
* LLM: OpenRouter model `deepseek/deepseek-v4-flash`.
* Embeddings: the Graphiti compatible embedding configuration already provisioned on VPS2.
* Namespace: `amb-graphiti-vps2-smoke-20260910`.
* The episode contains a unique marker and a known fact, without any benchmark gold labels.
* No AMB quality score or leaderboard row is produced by this smoke.

# Pass criteria

1. The setup command exits zero and reports the exact pinned commit.
2. The locked upstream environment installs without a dependency or import error.
3. The official MCP server answers the handshake and publishes every allowed Graphiti read tool.
4. `get_status` succeeds against the graph database.
5. `add_memory` returns a successful queued response.
6. `get_episodes` observes the submitted episode within the bounded wait.
7. `search_memory_facts` or `search_nodes` returns evidence tied to the submitted marker.

# Reproduction

Run the VPS2 smoke runner recorded with the result artifact. Do not use this record for a quality
comparison without a new preregistration that fixes the task set, seeds, model settings, and
analysis before measurement.

