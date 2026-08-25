# agent-memory-bench

A preregistered, execution-graded benchmark of pluggable **memory layers for coding agents**,
measured by **task success on real coding tasks executed by Claude Code**.

Existing memory benchmarks ask a model questions about synthetic conversations and let an LLM
judge the answers. This one gives a real agent real work in a real repository, where success
depends on something learned in earlier sessions, and grades the artifact by execution: tests
pass or they do not. No judge anywhere in the primary endpoint.

## Status

The benchmark includes a preregistered oracle and proactive retrieval diagnostic. See
[`docs/ORACLE_PREFETCH_DIAGNOSTIC.md`](docs/ORACLE_PREFETCH_DIAGNOSTIC.md) and
[`preregistration/003-oracle-prefetch-diagnostic.md`](preregistration/003-oracle-prefetch-diagnostic.md).
The two diagnostic arms are reference tracks and are not ranked as products.

Phase 0: harness bring-up. Nothing here is a result yet. The first preregistered run will be
announced before it happens, not after.

## Design in six decisions

1. **Official integrations, frozen and vendor-reviewed.** Every product enters through its own
   published Claude Code integration (plugin, MCP server, or lifecycle hooks). Each adapter's
   config is hash-pinned in `adapters/<name>/config.frozen.json`, and each vendor is publicly
   invited to review it before the run (`adapters/<name>/VENDOR_REVIEW.md` records the
   invitation, the response, or the documented silence).
2. **Additive design.** Every memory arm is the same CLAUDE.md bundle plus that product. The
   baseline is `claude_md`, not `bare`: nobody runs a coding agent memory-free.
3. **One neutral experience feed, each product's own write path.** The corpus is verbatim
   recorded agent session transcripts. Every adapter ingests identical bytes; what its
   extraction pipeline keeps is part of what is measured.
4. **Executable endpoints only.** Checkers run the artifact against oracles the sandbox never
   contained. A do-nothing session scores zero. Every task ships a naive reference solution
   that must fail and an informed one that must pass, asserted in CI.
5. **The admission gate.** A grid cell is discarded, not scored, unless every arm can PROVE its
   treatment was applied: MCP tools listed at session init, lifecycle hooks demonstrably fired
   with output, sandbox files digest-verified, and no arm holding another arm's tools. Discard
   counts are published per arm.
6. **Costs are end-to-end.** Ingestion tokens and session tokens land in one per-arm ledger
   (`harness/costs.py`), alongside wall time and negative-transfer counts. Deltas below the
   preregistered minimum effect are reported as noise.

## Arms

`bare`, `claude_md` (designated baseline), `fs_grep` (transcripts on disk plus grep),
`recall`, `mem0`, `supermemory`, `zep` (Graphiti), `cognee`.

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

Real runs need a Claude Code CLI of at least 2.1.221 (below that, a pending MCP server runs
the session without its tools while reporting success; the gate exists because that happened)
and the arm-specific credentials listed in `.env.example`. Docker one-command reproduction is
part of Phase 0 and lands in `docker/`.
