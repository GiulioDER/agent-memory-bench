# official-004-graphiti: Graphiti vendor entry on VPS2

Status: DRAFT until committed; frozen above the results marker before the first official session.

## Question

On the present AMB corpus, does the Graphiti memory arm change task success relative to the
`claude_md` static bundle and the `bare` control when all three arms use the same model, task
selection, seed set and matched memory protocol?

## Arms and fixed configuration

| arm | integration | admission surface |
|---|---|---|
| `bare` | no memory integration | negative checks only |
| `claude_md` | per-task static bundle | negative checks and recorded prompt digest |
| `graphiti` | official upstream Graphiti MCP server over stdio | `mcp__graphiti__` read and status tools |

Graphiti is pinned to upstream commit
`4bd728790e836950c3922e84f6f989f1380f54f2`, with the official `mcp_server` project and its
lockfile. The database is disposable FalkorDB 4.20.4 loaded into a user-owned Redis 8.10.1
process on VPS2. The VPS2 system Redis service is not used or modified. The LLM route is
OpenRouter `deepseek/deepseek-v4-flash`. The Graphiti embedder route is OpenRouter's
OpenAI-compatible `openai/text-embedding-3-small` endpoint. Credentials remain in the VPS2
secret file and are never written to the repository or participant environment.

The Graphiti corpus write uses only the official upstream `add_memory` tool before measurement.
The participant receives no write or destructive tool. Its allowed tools are exactly
`search_memory_facts`, `search_nodes`, `get_episodes`, `get_episode_entities`,
`get_entity_edge` and `get_status`, under the `mcp__graphiti__` prefix. The adapter waits for
episode visibility through `get_episodes` before sessions begin.

## Grid

The `present` condition is selected by `scripts.abstention.selection_for`, which currently yields
these 27 task IDs, including the explicitly selected `fa-dedup-key` task:

`fa-dedup-key`, `ts-atomic-write`, `ts-base36-id`, `ts-bom-merge`, `ts-casefold-sort`,
`ts-cli-exitcode`, `ts-config-layer`, `ts-crlf-export`, `ts-dedup-order`, `ts-empty-input`,
`ts-golden-regen`, `ts-idempotent-run`, `ts-ignore-gen`, `ts-json-sorted`, `ts-legacy-hash`,
`ts-log-mask`, `ts-manifest-rel`, `ts-mig-name`, `ts-natural-order`, `ts-nfc-count`,
`ts-quote-shell`, `ts-retry-cap`, `ts-round-money`, `ts-schema-additive`, `ts-semver-pin`,
`ts-stable-sort`, `ts-tz-utc`.

27 tasks x 5 seeds x 3 arms = 405 sessions. The model is
`deepseek/deepseek-v4-flash`, accessed through the AMB trusted model broker. Claude Code CLI is
the VPS2 Linux installation, and each session has a 600 second timeout. The memory instruction
variant is `protocol`, so the shared protocol is byte-identical across memory arms and each
vendor contributes only its capped result-schema appendix. `AMB_BLOCK_CONCURRENCY=1` is fixed.
Participant execution uses the verified rootless Docker policy with the benchmark network and
oracle isolation enabled. Docker access is denied to participants.

The exact runner is:

```bash
.venv/bin/python -m scripts.abstention \
  --run-id official-004-graphiti \
  --namespace amb-graphiti-official-004 \
  --conditions present \
  --arms bare,claude_md,graphiti \
  --seeds 5 \
  --model deepseek/deepseek-v4-flash \
  --memory-instruction protocol \
  --resume \
  --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

Execution is detached on VPS2 only after the preflight has proved the model broker, Graphiti
status, allowed tool list and corpus floor. The namespace and run ID are new and must not be
reused. The run is not a replication of official-003 because it adds Graphiti, uses the matched
protocol variant and measures the present condition only.

## Endpoints, in reporting order

1. Primary: paired per-task success for `graphiti` versus `claude_md`, with `bare` as the control;
   report per-task cluster bootstrap confidence intervals and exact paired discordance.
2. Secondary: Graphiti versus `bare` using the same admitted cells.
3. Mechanism: Graphiti search rate, search tool mix, successful MCP calls, episode visibility,
   entity and fact evidence counts, and the rate at which a retrieved result contains the task's
   governing session marker. A search is counted only from captured participant stream evidence.
4. Integrity: admitted and discarded cells, setup checks, prompt and configuration digests,
   corpus manifest digest, model and CLI versions, wall time, tokens and estimated cost.

An episode that is visible but produces no relationship edge is not counted as a fact hit. It is
reported as a valid episode or node retrieval where applicable. This preserves the observed
Graphiti behavior from the live smoke test instead of silently treating every successful write as
a fact-search success.

## Predictions

1. The Graphiti setup and preflight will pass, with all six allowed read and status tools exposed.
2. Graphiti will search in at least 50% of admitted sessions and will produce a nonzero node or
   episode evidence rate.
3. Graphiti's mean task success will be within 0.10 of `claude_md`; the direction is uncertain
   before measurement.
4. Graphiti will not show a statistically significant paired difference from `bare` at the
   0.05 threshold in this five-seed vendor-entry run.
5. Fewer than 10% of task-seed cells will be discarded, excluding a cell only when the harness
   admission gate says an arm did not complete or did not expose its declared surface.

## Exclusion and truncation rules

The existing AMB admission gate is frozen. A cell is admitted only when all three arms produce
valid records and matching setup metadata. A session error is a discard, not a zero. No task may
be removed after launch. If the $6.00 hard cap is reached, stop starting new cells and truncate
unstarted seeds in descending seed order, while publishing every completed record and the exact
discard set. A partial run is never resumed into a mixed condition; it must be archived and
registered again.

The run is falsified as preregistered if the task selection, model, seed count, memory variant,
Graphiti tool allowlist or VPS2 database configuration differs from this record, or if the setup
gate permits sessions after a failed preflight.

<!-- results are appended below this line; everything above is frozen -->
