# 041: Claude-Mem qualification and additive leaderboard candidate

Status: FROZEN before any live Claude-Mem worker, ingestion, or model session.

## Question

Can the pinned Claude-Mem Claude Code integration be admitted as an additive arm on the frozen
AMB official grid without a wiring, isolation, or corpus-ingestion failure?

## Treatment and frozen vendor version

The product is Claude-Mem, now branded Grok Mem in the upstream README while retaining the
`claude-mem` package name. The adapter uses the official plugin repository
`https://github.com/thedotmack/claude-mem`, tag `v13.24.0`, commit
`ffe75a81e71b190644195a0ae9a5b6997757317c`, and the plugin's shipped lifecycle hooks and MCP
search server.

The adapter copies the pinned plugin into the session's isolated `CLAUDE_CONFIG_DIR`. It uses the
vendor's documented worker import endpoint for the frozen transcript feed, and a direct Node
invocation of the shipped MCP server script so the integration does not depend on the upstream
shell resolver under the Windows benchmark host. That path change is recorded as adapter wiring,
not as an upstream file modification.

## Comparison and grid

The eventual leaderboard submission will use the frozen `official-003` base, the same task roster,
five conditions (`absent`, `superseded`, `contradictory`, `adjacent`, `present`), five session
seeds, model `deepseek/deepseek-v4-flash`, `protocol` instructions, and the base run's timeout,
CLI version, pricing, and admission rules. The qualification phase may use a smaller explicitly
named subset, but cannot produce a leaderboard score.

The comparison baseline is the joined `claude_md` arm from `official-003`. The candidate is not
eligible for the public product roster until the full additive submission passes the join and
verification checks.

## Endpoints, in reporting order

1. Primary qualification endpoint: every required Claude-Mem MCP server and lifecycle hook is
   observed in the session evidence, with zero hook errors and an isolated data directory.
2. Corpus endpoint: the vendor import route accepts the complete frozen corpus and returns the
   expected imported observation count; a search through the official worker returns a hit.
3. Additive leaderboard endpoint, only after qualification: execution-graded task success versus
   the joined `claude_md` baseline, with per-task cluster bootstrap confidence intervals.
4. Mechanism metrics: search-call rate, context-injection rate, hook reachability, imported item
   count, worker/provider identity, ingestion wall time, and any separately metered observer cost.

## Predictions

1. The pinned MCP server will expose `search`, `timeline`, and `get_observations`, and the worker
   import route will load the static corpus. The main risk is Windows hook execution, not missing
   product capability.
2. SessionStart and UserPromptSubmit will be reachable in nearly all otherwise healthy sessions;
   PostToolUse and Stop will be reachable when the corresponding Claude Code lifecycle event is
   emitted. Any nonzero hook exit or missing injected output makes that session inadmissible.
3. Claude-Mem will be a viable leaderboard addition if its official retrieval surface reaches at
   least the frozen baseline's search rate and its admitted-cell rate is at least 0.95. These are
   qualification gates, not post-hoc score selection rules.

## Exclusion and truncation rules

The repository admission gate decides eligibility before outcome aggregation. A missing MCP tool,
unhealthy MCP server, missing required hook, nonzero hook exit, hook-reported error, wrong config
digest, data-path escape, or failed import verification discards the cell rather than turning an
integration failure into a product score. If a run must be shortened for budget, seeds are
truncated in reverse order and tasks are never selectively removed.

## What would falsify this

The candidate is not suitable for the leaderboard if the pinned official path cannot run on the
benchmark host, if the vendor import route cannot load the frozen feed, if project scoping makes
the imported memories unavailable to the measured sessions, or if fewer than 95 percent of the
candidate's cells are admissible after the frozen gate.

<!-- results are appended below this line; the frozen protocol above is never edited -->
