# Supermemory vendor review invitation

Dear Supermemory team,

I am writing to invite you to review Supermemory's preliminary results in the Agent Memory Benchmark, or AMB.

AMB measures the real effect of memory systems on coding agents. Unlike benchmarks that measure only whether a system retrieves a relevant document, AMB evaluates the complete agent session and checks whether the resulting code actually works. Retrieval alone is not sufficient, because retrieved information can either improve an agent's decisions or introduce misleading context and damage the session.

I have completed the Supermemory run `supermemory-003`. The current result covers 313 cells joined to the frozen `official-003` benchmark run, with a task success rate of 20.77%. The search rate is reported separately as a diagnostic because Supermemory's official Claude Code integration retrieves through lifecycle hooks rather than an explicit memory tool.

I would be grateful if you could review:

1. The Supermemory adapter and its integration path.
2. The frozen configuration and version pins.
3. The ingestion and lifecycle-hook retrieval design.
4. The published run artifacts and recorded results.

The relevant materials are available here:

Benchmark repository:
[https://github.com/GiulioDER/agent-memory-bench/tree/codex/supermemory-leaderboard-20260905](https://github.com/GiulioDER/agent-memory-bench/tree/codex/supermemory-leaderboard-20260905)

Adapter configuration:
[https://github.com/GiulioDER/agent-memory-bench/blob/codex/supermemory-leaderboard-20260905/adapters/supermemory/config.frozen.json](https://github.com/GiulioDER/agent-memory-bench/blob/codex/supermemory-leaderboard-20260905/adapters/supermemory/config.frozen.json)

Adapter implementation:
[https://github.com/GiulioDER/agent-memory-bench/blob/codex/supermemory-leaderboard-20260905/adapters/supermemory/adapter.py](https://github.com/GiulioDER/agent-memory-bench/blob/codex/supermemory-leaderboard-20260905/adapters/supermemory/adapter.py)

Run summary:
[https://github.com/GiulioDER/agent-memory-bench/blob/codex/supermemory-leaderboard-20260905/results/supermemory-003/arm_summary.json](https://github.com/GiulioDER/agent-memory-bench/blob/codex/supermemory-leaderboard-20260905/results/supermemory-003/arm_summary.json)

Comparison report:
[https://github.com/GiulioDER/agent-memory-bench/blob/codex/supermemory-leaderboard-20260905/reports/supermemory-003-vs-recall.md](https://github.com/GiulioDER/agent-memory-bench/blob/codex/supermemory-leaderboard-20260905/reports/supermemory-003-vs-recall.md)

Frozen run protocol:
[https://github.com/GiulioDER/agent-memory-bench/blob/codex/supermemory-leaderboard-20260905/preregistration/039-supermemory-official-leaderboard.md](https://github.com/GiulioDER/agent-memory-bench/blob/codex/supermemory-leaderboard-20260905/preregistration/039-supermemory-official-leaderboard.md)

I am planning to publish the result on or around 19 September 2026. If you identify an error, unfair configuration choice, missing information, or any other issue that should be addressed before publication, please reply with the details before that date. If a correction or replacement run is justified, I will preserve the current result and publish any replacement separately with its own configuration and provenance.

Kind regards,

Giulio D’Erme
