# agent-memory-bench

A preregistered, execution-graded benchmark of pluggable **memory layers for coding agents**,
measured by **task success on real coding tasks executed by Claude Code**.

Existing memory benchmarks ask a model questions about synthetic conversations and let an LLM
judge the answers. This one gives a real agent real work in a real repository, where success
depends on something learned in earlier sessions, and grades the artifact by execution: tests
pass or they do not. No judge anywhere in the primary endpoint.

## Status

Phase 0: harness bring-up. The first preregistered multi-product run will be announced before it
happens, not after.

**Four limits that bound every number published so far.** They are here rather than in a footnote
because a reader who does not know them will over-read the results.

1. **Only the READ path is measured.** `corpus/` is 125 pre-authored transcripts, bulk ingested
   once before the grid and never written to again. The agent never forms a memory from its own
   work, so half of every product under test is unmeasured, and it is the half products whose value
   is extraction and consolidation actually sell.
   [`preregistration/006`](preregistration/006-longitudinal-suite.md) is the design that would
   measure it; it has not run.
2. **`claude_md` is the fixture's orientation README, not a curated conventions file.** It is a
   floor with a document attached, not the realistic incumbent, and on `ts-legacy-hash` it actively
   names the wrong helper (`bare` 1.00 against `claude_md` 0.00 in two runs).
3. **The memory arm is not budget-matched.** On `pilot-004-placebo` the recall arm used 4.5x the
   input tokens and 2.6x the wall time of every other arm. `costs.json` now carries
   success-per-million-tokens per arm; there is still no arm run at a matched budget.
4. **One model, and it is a cheap one.** Everything is `deepseek/deepseek-v4-flash`. The one
   attempt at a stronger model failed on provider credit and has not been rerun.

The benchmark includes a preregistered oracle and proactive retrieval diagnostic. See
[`docs/ORACLE_PREFETCH_DIAGNOSTIC.md`](docs/ORACLE_PREFETCH_DIAGNOSTIC.md) and
[`preregistration/003-oracle-prefetch-diagnostic.md`](preregistration/003-oracle-prefetch-diagnostic.md).
The two diagnostic arms are reference tracks and are not ranked as products.

An adversarial audit of this benchmark, written against it rather than for it, is in
[`docs/audit/2026-08-28-adversarial-benchmark-audit.md`](docs/audit/2026-08-28-adversarial-benchmark-audit.md).

## Design in six decisions

1. **Official integrations, frozen and vendor-reviewed.** Every product enters through its own
   published Claude Code integration (plugin, MCP server, or lifecycle hooks). Each adapter's
   config is hash-pinned in `adapters/<name>/config.frozen.json`, and each vendor is publicly
   invited to review it before the run (`adapters/<name>/VENDOR_REVIEW.md` records the
   invitation, the response, or the documented silence).
2. **Additive design, with the instruction controlled too.** Every memory arm is the same
   CLAUDE.md bundle plus that product, plus `adapters/_shared/memory_protocol.md` **byte-identical
   across arms**, plus that product's own result-schema appendix capped at 1,200 bytes. The
   instruction is a treatment: until 2026-08-28 the recall arm carried 5,428 characters of it and
   `fs_grep` 231, and most of the difference was generic coaching that would have helped any arm.
   Per-arm instruction sizes are published in every run's `environment.json`.
3. **One neutral experience feed, each product's own write path.** The corpus is verbatim
   recorded agent session transcripts. Every adapter ingests identical bytes; what its
   extraction pipeline keeps is part of what is measured.
4. **Executable endpoints only.** Checkers run the artifact against oracles the sandbox never
   contained. A do-nothing session scores zero. Every task ships a naive reference solution
   that must fail and an informed one that must pass, asserted in CI.
5. **The admission gate.** A grid cell is discarded, not scored, unless every arm can PROVE its
   treatment was applied: MCP tools listed at session init, lifecycle hooks demonstrably fired
   with output, every arm's sandbox digest equal to every other's, and no arm holding another
   arm's tools. Discard counts are published per arm.

   Two disclosures the gate cannot make for itself. Only an arm with a memory surface can FAIL to
   wire, so the discard rule protects one class of arm's worst outcome and no other's; run
   `scripts/discard_sensitivity.py` for the intention-to-treat column beside every headline. And a
   timeout is an outcome, not a wiring fault: it is never retried, and the retry kind is recorded
   per attempt so the counts are publishable per arm.
6. **Costs are end-to-end.** Ingestion tokens and session tokens land in one per-arm ledger
   (`harness/costs.py`), alongside wall time, success-per-million-tokens, and negative-transfer
   counts. An arm that ingests with a model on the benchmark host reports zero hosted tokens and
   names the model, so its zero is never read as a zero cost beside a competitor's extraction
   bill. Deltas below the preregistered minimum effect are reported as noise.

## Arms

Implemented and runnable today: `bare`, `claude_md` (designated baseline), `placebo`
(length-matched neutral prose), `protocol` (the memory instruction with no memory layer, which is
what separates the coaching from the retrieval), `fs_grep` (transcripts on disk plus grep), and
`recall`.

Prepared and pending smoke verification: `supermemory`. The adapter uses the pinned official
Claude Code plugin, Supermemory Local by default, and an isolated lifecycle-hook config. It is not
called runnable or ready until the preregistered smoke test admits every arm and projects the full
run below five hours. `mem0`, `zep` (Graphiti), and `cognee` remain unbuilt here.

Disclosure: this benchmark is built by the authors of recall, which competes in it. That is
exactly why the methodology is preregistered, the harness is open, every adapter config is
vendor-reviewable before any run, and all results are published including the ones recall
loses. The full run's protocol is committed under `preregistration/` before a single session
starts.

## Layout

| path | what |
|---|---|
| `harness/` | engine: Claude Code executor, sandbox, admission gate, grid runner, paired stats, cost ledger |
| `harness/adapters/base.py` | the `MemoryAdapter` contract every arm implements |
| `adapters/<name>/` | one product: adapter code, frozen config, vendor-review record, version pins |
| `corpus/` | the neutral experience feed: verbatim session transcripts, sha256 manifest |
| `tasks/<id>/` | fixture tree, task spec, executable checker, naive and informed references |
| `oracles/<id>/` | checker inputs the sandbox never contains |
| `preregistration/` | committed before measuring; a guard blocks runs while it is dirty |
| `results/<run_id>/` | full per-session logs, streams, admission verdicts, costs |

## Running

```bash
python -m pytest tests/ -q
```

Static checks, no credentials and no model calls:

```bash
python -m scripts.audit_corpus && python -m scripts.audit_plants
python -m scripts.pilot --dry-run --arms bare,claude_md,recall
```

Real runs need a Claude Code CLI of at least 2.1.221 (below that, a pending MCP server runs
the session without its tools while reporting success; the gate exists because that happened)
and the arm-specific credentials listed in `.env.example`.

⚠️ **A third party cannot currently reproduce the `recall` arm.**
`adapters/recall/config.frozen.json` carries `"package_pin": "TBD"`, and the published runs
resolved `recall` from a local checkout through `PYTHONPATH`, so the exact version that produced
the numbers is not recorded. `docker/compose.yaml` brings up a pgvector database and the harness
image; it does not install or start a memory server. Both are Phase 3 work and neither is done.
Sandboxes are built outside this repository (`harness.sandbox.default_work_root`, override with
`AGENT_MEMORY_BENCH_WORK_ROOT`), because a sandbox under `results/` can reach `oracles/` with one
`cd ..`.
