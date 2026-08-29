# agent-memory-bench

A preregistered, execution-graded benchmark of pluggable **memory layers for coding agents**,
measured by **task success on real coding tasks executed by Claude Code**.

Existing memory benchmarks ask a model questions about synthetic conversations and let an LLM
judge the answers. This one gives a real agent real work in a real repository, where success
depends on something learned in earlier sessions, and grades the artifact by execution: tests
pass or they do not. No judge anywhere in the primary endpoint.

## Status

Phase 0: harness bring-up and internal pilots. The first preregistered multi-product run will be
announced before it happens, not after.

**Where the benchmark actually stands, dated, with the command that re-derives each claim, is
[`docs/STATUS.md`](docs/STATUS.md).** As of 2026-08-29: six arms run and four do not, the suite
holds 30 executable tasks, eleven of them carry all four harm conditions, five internal pilots
have run (four on one cheap model, one incomplete on a stronger one), and no multi-product run
has happened. Every run a committed document cites is now in `results/`, along with the harm
suite's first run and one diagnostic; **none of those is written up under its preregistration
yet, so no number from them is quoted anywhere.** `docs/STATUS.md` lists what is published and
what is still held back.

Three things landed in the week to 2026-08-29, and each changes how the earlier numbers must be
read.

1. **The instruction stopped being a confound.** Until 2026-08-28 the recall arm carried 5,428
   characters of behavioural instruction while `fs_grep` carried 231 and the static arms carried
   none, and most of that difference was generic agent coaching that would have helped any arm.
   Every memory arm now receives `adapters/_shared/memory_protocol.md` byte-identical, plus its
   own result-schema appendix capped at 1,200 bytes, and the `protocol` arm exists to separate
   the coaching from the retrieval. Per-arm instruction sizes are published in every run's
   `environment.json`. **Every published number predates this change**, so every result in this
   repository was measured under the old instruction budget.
2. **Three protocol-sensitive fixes**, each of which moves a number a frozen preregistration
   rests on, landed together with the break stated rather than absorbed: a grader that rejected
   correct solutions about 40% of the time, a checker crash that discarded the whole paired cell
   instead of failing one arm, and cost estimates that charged cache reads at the fresh-input
   rate.
   ⚠️ **A rerun is therefore no longer protocol-identical to the frozen runs.** Rerun both arms
   of any model comparison, or say in the report that the contrast is measured on a revised
   instrument.
   [`docs/audit/2026-08-29-protocol-change-record.md`](docs/audit/2026-08-29-protocol-change-record.md).
3. **Run prices are required, not defaulted.** Three runners carried three different defaults and
   none matched the frozen rates, so any run launched without the flags was priced on a basis
   nobody chose. Compare runs on tokens, never on the dollars of two runs priced differently.

**Five limits that bound every number published so far.** They are here rather than in a footnote
because a reader who does not know them will over-read the results.

1. **Only the READ path is measured. Half of every product under test is unmeasured, and it is the
   half that extraction and consolidation products sell.** `corpus/` is 195 pre-authored
   transcripts, bulk ingested once before the grid and never written to again. The agent never
   forms a memory from its own work, so nothing here says whether a product captures what an agent
   learns, or whether what it captured survives to the next session.
   [`preregistration/006`](preregistration/006-longitudinal-suite.md) is the design that would
   measure it; it has not run.

   **Consequence for how results are titled:** no multi-product ranking will be published until
   that suite has run. A ranking of memory products measured on read-only bulk ingest is a ranking
   of retrieval engines, and if one ships before the longitudinal suite it will say so in its
   title.
2. **The suite favoured retrieval over summarisation, and a competitor saying so would be right.**
   All 30 `ts-*` tasks put one discrete governing fact in one document, which is retrieval at its
   best case and gives a product that extracts and consolidates at write time no way to win and
   every way to lose: every fact it drops at write time is an unrecoverable loss, while a verbatim
   index keeps everything retrievable. The single discrete governing fact is the mechanism.
   Three `xs-*` tasks now exist whose governing fact no single session states, in three shapes
   (two halves joined, a value revised across three dated sessions, a rule widened later by a
   session that restates none of it):
   [`docs/CROSS_SESSION_SYNTHESIS.md`](docs/CROSS_SESSION_SYNTHESIS.md) and
   [`preregistration/011`](preregistration/011-cross-session-synthesis.md). Their sessions were
   recorded on 2026-08-29 as pipeline validation rather than as run corpus and are now in the
   feed, but the suite has not run, so this limit is answered structurally and not yet
   empirically.
3. **`claude_md` is the fixture's orientation README, not a curated conventions file.** It is a
   floor with a document attached, not the realistic incumbent, and on `ts-legacy-hash` it actively
   names the wrong helper (`bare` 1.00 against `claude_md` 0.00 in two runs).
4. **The memory arm is not budget-matched.** On `pilot-004-placebo` the recall arm used 4.5x the
   input tokens and 2.6x the wall time of every other arm. `costs.json` now carries
   success-per-million-tokens per arm; there is still no arm run at a matched budget.
5. **One model, and it is a cheap one.** Everything is `deepseek/deepseek-v4-flash`. The one
   attempt at a stronger model failed on provider credit and has not been rerun.

The benchmark includes a preregistered oracle and proactive retrieval diagnostic. See
[`docs/ORACLE_PREFETCH_DIAGNOSTIC.md`](docs/ORACLE_PREFETCH_DIAGNOSTIC.md) and
[`preregistration/003-oracle-prefetch-diagnostic.md`](preregistration/003-oracle-prefetch-diagnostic.md).
The two diagnostic arms are reference tracks and are not ranked as products.

### The harm suite, because helping and not harming are different questions

Every one of the original 24 tasks places its governing fact **in** the corpus, so the suite as
it stood could only ask whether memory helps. It was structurally incapable of detecting harm,
and an arm that helps 20% of cells while harming 15% reported the same headline as one that
helps 20% and harms 2%.

[`preregistration/005-abstention-suite.md`](preregistration/005-abstention-suite.md) adds four
corpus conditions, each defined by **what the planted corpus contains** and never by what any
system does about it: `absent`, `superseded`, `contradictory`, and `adjacent`. Damage is failing
a cell the `bare` arm solved.

As of 2026-08-29, 12 tasks carry plants and **11 of them carry all four conditions**, above the
threshold of eight that 005 sets for reporting a condition as a result rather than as
underpowered. What building the last two conditions cost is in
[`docs/PLANTING_ADJACENT_AND_CONTRADICTORY.md`](docs/PLANTING_ADJACENT_AND_CONTRADICTORY.md).
**`abstention-001` is published as an artifact and is still not a result.** Its two conditions,
their records and all four computed endpoints are committed under `results/`. Neither
preregistration 005 nor 010 carries an appended results section, so nothing has been written up,
defended or interpreted, and **no abstention number should be quoted from anywhere.** The suite's
other two conditions have not been run at all.

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
   that must fail and an informed one that must pass, asserted in CI. A task whose fact is
   distributed across sessions ships one more per shard, holding that shard alone, and CI asserts
   each of those fails too: that is what makes "no single session suffices" a checked property
   rather than a design note.
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

## Tasks

**30 executable `ts-*` tasks.** The frozen pilot grid used 24 of them; six more were added by
[`preregistration/008-midband-task-calibration.md`](preregistration/008-midband-task-calibration.md)
and calibrated against the `bare` arm on 2026-08-27.

That calibration is worth reading for its result rather than its output. It was designed to
produce tasks in the mid-band, where both help and harm are visible, and one of six landed there
against a prediction of three. The record scores the miss: agent convention-following turned out
to be close to deterministic per convention, and what separates a convention the model gets right
from one it gets wrong is whether the convention is visible in the output of a **single run**.
Cross-invocation properties are the blind spot, and that was not derivable from the tasks the
design rule came from.

## Arms

Implemented and runnable today: `bare`, `claude_md` (designated baseline), `placebo`
(length-matched neutral prose), `protocol` (the memory instruction with no memory layer, which is
what separates the coaching from the retrieval), `fs_grep` (transcripts on disk plus grep), and
`recall`.

**Not built yet:** four third-party memory products. Those four are not named yet. Every
vendor is invited to review its own adapter and frozen config before any measured run, no
invitation has gone out, and naming a product first would enter it into a benchmark nobody
has told it about. They are named when the first preregistered run is announced, which is
before the run rather than after it.

Their `adapters/<name>/` directories currently hold a docstring and no `adapter.py`, no
`VENDOR_REVIEW.md` exists for any adapter including `recall`, and no `versions.lock` exists
either. Nothing here is a multi-product comparison until those land.

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
| `tasks/<id>/` | fixture tree, task spec, executable checker, naive and informed references (plus `partial_*` for a distributed fact) |
| `oracles/<id>/` | checker inputs the sandbox never contains |
| `preregistration/` | committed before measuring; a guard blocks runs while it is dirty |
| `results/<run_id>/` | full per-session logs, streams, admission verdicts, costs |
| `docs/` | design notes and dated records; [`docs/STATUS.md`](docs/STATUS.md) is the state of the benchmark, `docs/audit/` the record of changes to the instrument |
| `reports/` | the written report for a completed run |
| `site/` | the published pages, deployed verbatim with no build step |

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

They also need the prices stated explicitly. Since 2026-08-29 every live run refuses without
them, because three runners carried three different defaults and none matched the frozen rates,
so a run launched without the flags was priced on a basis nobody chose. Dry runs need none, and
the refusal names the frozen rates so a run that means to match preregistration 002 copies one
line rather than hunting for it:

```bash
python -m scripts.pilot --run-id my-run --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

For the local Docker stack, copy `.env.example` to `.env`, set a unique `POSTGRES_PASSWORD`, and
run `docker compose --env-file .env -f docker/compose.yaml up --build`. Compose requires that
password instead of using a repository default.

### What a third party can reproduce today, and what they cannot

**Three arms reproduce completely**: `bare`, `placebo` and `claude_md` need only the Claude Code
CLI and a model key. That is the whole accessibility floor of this benchmark and it works, for
roughly the price of a coffee across the full grid.

**`mempalace` reproduces** with `pip install mempalace==3.8.0` and the two variables in
`.env.example`, which is where they were missing until 2026-08-30.

⚠️ **`recall` does not reproduce, and the reason changed on 2026-08-30.** The old blocker here
was that its `package_pin` read `TBD` and published runs resolved recall from a local checkout
through `PYTHONPATH`. Both are fixed: the arm is pinned to a released
`recall-rag[fastembed,mcp,voyage]==0.11.0` from PyPI, installed into an isolated environment.

The blocker now is that `adapters/recall/config.frozen.json` encodes **one specific host**. Its
`ssh_host`, `remote_root`, `remote_python`, `remote_env_file` and `dsn` all name paths on the
machine the official run executes on, because the corpus and the serving database live there.
Nothing about that is portable, and moving the harness onto the serving host made it less
portable rather than more.

Reproducing the recall arm therefore currently means supplying your own Postgres with pgvector,
your own Voyage key, building and calibrating your own generation with
`scripts/prepare_recall_corpora.py`, and rewriting five fields of a config that is deliberately
frozen. That is not a reproduction path, it is a rebuild. `docker/compose.yaml` brings up a
pgvector database and the harness image but installs and starts no memory server, so it does not
close the gap either.

**This is the honest state and it is the top of the Phase 3 list.** A benchmark whose own arm
cannot be re-run by a reader is asking for trust it has not earned, and this section exists so
nobody discovers that after spending money.
Sandboxes are built outside this repository (`harness.sandbox.default_work_root`, override with
`AGENT_MEMORY_BENCH_WORK_ROOT`), because a sandbox under `results/` can reach `oracles/` with one
`cd ..`.
