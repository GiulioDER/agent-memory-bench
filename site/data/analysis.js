/* Editorial pros and cons, WRITTEN BY HAND, keyed by the public arm name.

   Rendered under each product on leaderboard.html and in each product's section on
   analysis.html. Unlike data/leaderboard.js this file is opinion, not measurement, so it holds no
   number: tests/test_leaderboard_generated.py fails if a digit appears in any pro or con. The
   numbers that back them are generated, and the reasoning, dated and sourced, is on analysis.html. */
window.AMB_ANALYSIS = {
  "written": "2026-09-26",
  "vendors": {
    "RE-call": {
      "pros": [
        "Highest task success of the six products, and first in the present, absent and superseded conditions.",
        "Labels a stale hit as superseded and points to its replacement, and abstains when nothing clears its calibrated threshold.",
        "No extraction model at ingest: the corpus is embedded, not rewritten."
      ],
      "cons": [
        "Its interval still crosses zero, so the lead over claude_md is not established.",
        "No gain on contradictory or adjacent, the two conditions that test restraint.",
        "Several times the baseline's agent tokens per task, and its embedding bill is not in the ledger.",
        "Built by the author of this benchmark."
      ]
    },
    "Claude Mem": {
      "pros": [
        "Second highest task success, ahead of claude_md in four of five conditions and level with it on contradictory.",
        "Its first-search guard made the agent consult memory in almost every session.",
        "Search, timeline and observation tools let the agent widen a hit step by step instead of reading everything."
      ],
      "cons": [
        "The most agent tokens per task of any arm on the board, most of them context re-read on every turn.",
        "Measured with the first-search guard switched on, which is not the plugin's default.",
        "Ingest was not metered, so its store cost is missing from the comparison.",
        "Its interval crosses zero."
      ]
    },
    "cognee": {
      "pros": [
        "Best product on adjacent, the wrong-scope trap, and second on superseded.",
        "Agent-side cost close to the cheapest products.",
        "Builds a real knowledge graph of entities and relations, so answers can be grounded in structure rather than in one chunk."
      ],
      "cons": [
        "The largest bill on the board once ingest is counted: a model reads the whole corpus to build the graph.",
        "The most discarded cells of any product, nearly all because its MCP server failed to connect.",
        "The agent searched in fewer than a third of sessions.",
        "Below claude_md on absent, where there is nothing to find."
      ]
    },
    "Graphiti": {
      "pros": [
        "The cheapest product per task in agent tokens.",
        "Strong on absent, second only to RE-call.",
        "A temporal graph whose facts carry validity in time, which is the right design for knowledge that changes."
      ],
      "cons": [
        "The store it searched held only a small fraction of the corpus, after a crash recovery reused a partial ingest.",
        "The run deviated from its preregistration in several stated ways.",
        "The agent searched rarely, and there was no gain on superseded, where a temporal graph should help most.",
        "Ingest was not metered."
      ]
    },
    "mempalace": {
      "pros": [
        "Runs entirely on local hardware, with no hosted model at ingest or at query time.",
        "Stores conversations verbatim, so nothing is lost to summarisation.",
        "Second among the products on present, where a clean fact is there to find."
      ],
      "cons": [
        "The largest loss on contradictory of any product except supermemory.",
        "Among the higher agent token costs per task.",
        "Local ingest is slow, and its cost is time on the host rather than tokens."
      ]
    },
    "supermemory": {
      "pros": [
        "Needs no tool call: hooks inject context at session start and on every prompt.",
        "Self-hostable, with local embeddings and a local model.",
        "Level with claude_md on absent."
      ],
      "cons": [
        "The only product clearly worse than claude_md.",
        "Injected context into every session, including raw transcripts from unrelated projects presented as a persistent profile.",
        "Sessions often stopped before doing the task, and it collapsed on superseded and adjacent.",
        "Measured with raw transcripts as memories rather than its own extraction, which did not finish in time."
      ]
    }
  }
};
