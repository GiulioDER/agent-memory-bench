# Graphiti vendor review invitation

Dear Zep and Graphiti team,

My name is Giulio D'Erme. I am researching and developing agent memory layers for coding agents,
and I built the Agent Memory Benchmark, or AMB, to understand which approaches make a practical
difference in real coding work.

AMB tests the outcome of a complete coding session, not only whether a system retrieves a relevant
memory. Each arm receives the same task and corpus, the agent works through the task with its own
official integration, and an automated checker verifies whether the requested change actually
works. I chose this design because a retrieved memory can be useful, irrelevant, or actively
misleading. For an agent memory layer to be valuable, it should improve the final result reliably,
not merely return a plausible document.

I am particularly interested in Graphiti's approach to structured and temporal memory, and I would
welcome any collaboration, technical feedback, or suggestions that could make this comparison more
useful to the memory systems community.

The Graphiti arm has completed the `official-007-graphiti-bare` measurement using Graphiti's MCP
integration, the shared benchmark model, and the preregistered coding task protocol. The official
leaderboard now shows Graphiti by name with its results marked pending. No Graphiti score has been
released on the leaderboard while this review is open.

I would be grateful if you could review:

1. The Graphiti integration path and MCP server configuration.
2. The frozen model, embedder, database, and version settings used for ingestion and retrieval.
3. The corpus format and the condition specific transcripts supplied to the arm.
4. The admission rules, per session records, and the comparison methodology against the existing
   official run.

If you identify an incorrect configuration, a missing disclosure, an integration error, or any
other issue that could affect comparability, please reply with the details. I will preserve the
current artifacts and record any correction or replacement run separately with its own provenance.

The benchmark repository and replication instructions are available at:

* Benchmark repository: https://github.com/GiulioDER/agent-memory-bench
* Replication instructions: https://github.com/GiulioDER/agent-memory-bench/blob/master/docs/REPLICATION.md
* Leaderboard: https://giulioder.github.io/agent-memory-bench/leaderboard.html

The review window is open for two weeks from publication of this invitation. If no response is
received by the deadline, I will record that explicitly and publish the Graphiti result with the
complete per session artifacts and comparison report.

Kind regards,

Giulio D'Erme
