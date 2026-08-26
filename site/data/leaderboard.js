/* Leaderboard data. Loaded as a script so the page works on file:// and on Pages alike.
   A re-run updates this file and nothing else.

   `run` stays null until the first preregistered run publishes. When it lands, fill it and
   the per-arm fields; the page renders whatever is here without edits to the HTML.
   Numbers must come from results/<run_id>/, never typed from memory. */

window.AMB_LEADERBOARD = {
  updated: "2026-08-26",
  baseline: "claude_md",

  /* When official: { id: "run-001", date: "…", cli: "2.1.2xx", model: "…",
                      tasks: 24, sessionsPerCell: n, prereg: "preregistration/00x-….md" } */
  run: null,

  /* Product arms, the ranked table. success/delta as fractions (0.62), ci as [lo, hi],
     discarded as integer cells, tokensPerTask in thousands, costPerTask in USD. */
  arms: [
    { name: "recall",      type: "MCP server",               success: null, delta: null, ci: null, discarded: null, tokensPerTask: null, costPerTask: null },
    { name: "mem0",        type: "SaaS API",                 success: null, delta: null, ci: null, discarded: null, tokensPerTask: null, costPerTask: null },
    { name: "supermemory", type: "SaaS API",                 success: null, delta: null, ci: null, discarded: null, tokensPerTask: null, costPerTask: null },
    { name: "zep",         type: "Graphiti, local docker",   success: null, delta: null, ci: null, discarded: null, tokensPerTask: null, costPerTask: null },
    { name: "cognee",      type: "local docker",             success: null, delta: null, ci: null, discarded: null, tokensPerTask: null, costPerTask: null },
    { name: "fs_grep",     type: "transcripts on disk",      success: null, delta: null, ci: null, discarded: null, tokensPerTask: null, costPerTask: null, role: "control" },
    { name: "claude_md",   type: "CLAUDE.md bundle",         success: null, delta: 0,    ci: null, discarded: null, tokensPerTask: null, costPerTask: null, role: "baseline" },
    { name: "bare",        type: "no memory",                success: null, delta: null, ci: null, discarded: null, tokensPerTask: null, costPerTask: null, role: "floor" }
  ],

  /* Diagnostic reference tracks. Never ranked with products. */
  reference: [
    { name: "oracle_memory",  what: "exact evidence injected; ceiling control",            success: null, delta: null },
    { name: "recall_prefetch", what: "harness-side retrieval with the exact task prompt",  success: null, delta: null }
  ]
};
