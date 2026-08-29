# official-001: RE-call against MemPalace, on a corpus built to mislead both

Status: DRAFT until committed; a committed record is frozen above the results marker.

**These numbers are intended for publication.** Everything below is fixed before the first session.

## Question

On four corpus conditions where retrieved evidence is absent, superseded, contradictory or
inapplicable, does either memory product change a coding agent's task success, and does either
decline to answer when its corpus cannot support one?

## Arms

Six. Each product enters through its own published integration, configured as its own
documentation recommends, with the same corpus bytes.

| arm | treatment | role |
|---|---|---|
| `bare` | nothing | reference. Damage is defined against it and it is mandatory |
| `placebo` | text with no memory content | separates "memory helped" from "any extra context helped" |
| `claude_md` | fixture README bundle | static-instruction control |
| `protocol` | the shared memory protocol, no memory surface | isolates the INSTRUCTION from the retrieval |
| `recall` | `recall-rag[fastembed,mcp,voyage]==0.11.0` | product under test |
| `mempalace` | `mempalace==3.8.0` | product under test |

`fs_grep`, `oracle_memory` and `recall_prefetch` are **excluded**. The first by decision; the other
two are adapters the runner does not register as arms, and adding them is a code change that
belongs in its own record. `oracle_memory` is the ceiling control and `recall_prefetch` isolates
the decision to search, and both are named here so their absence is a recorded choice rather than
an oversight.

## Grid

Ten planted tasks, three seeds, four conditions, model `deepseek/deepseek-v4-flash` via OpenRouter.
`contradictory` runs on nine tasks (`ts-base36-id` declares none; see its
`PLANTS-NOT-IMPLEMENTED.md`). Sessions: `(30 + 30 + 27 + 30) x 6 =` **702**.

## Both products get their full Claude Code surface, and neither gets to write

This is the fairness condition, and it is symmetric by construction.

* **Skills**: each arm loads the skills its own package ships. recall ships two
  (`check-memory-before-acting`, `keep-memory-current`); MemPalace ships two under
  `.claude-plugin/skills/`.
* **Read and navigation tools**: each arm gets its product's full read surface. MemPalace's 20
  include its entire knowledge graph (`kg_query`, `traverse`, `follow_tunnels`, `graph_stats`,
  `mesh_peers`); recall's therefore include its reasoning and graph tools alongside
  `recall_search` and `recall_evidence`. ⚠️ Running recall with only two tools, as
  `abstention-002` did, was the ASYMMETRIC configuration, against recall.
* **Write tools and write hooks are withheld from BOTH.** Both products ship write-side Claude Code
  hooks (recall: `SessionEnd`, `PreCompact`; MemPalace: session-end, precompact, stop). Verified:
  recall's `SessionEnd` calls `index_memory_directory` on `<cwd>/memory`. The corpus is frozen
  after ingest and no runner calls `snapshot`/`restore` per cell, so a session that wrote would
  change what the next seed reads, and a cell that solved a task could write its answer where the
  next cell retrieves it. This is the policy already recorded in MemPalace's `VENDOR_REVIEW.md`.

## recall's configuration, and why each setting is what it is

Measured on the `absent` corpus (633 chunks, 121 sources) through the MCP server, against the
held-out query set of 46 labelled queries drawn from the 21 tasks that are never a benchmark
subject.

| setting | value | why |
|---|---|---|
| version | `0.11.0`, PyPI, isolated venv on VPS2 | a published artefact, not a checkout. See 012/013 |
| embedder | `voyage:voyage-4`, 1024d | chosen for representativeness. See the caveat below |
| environment | `RECALL_ENV=production` | the ONLY switch that routes search through `GenerationStore`, so it is the only way a calibrated corpus is served as calibrated |
| trust | strict (`RECALL_TRUST_MODE` unset) | the shipped default |
| calibration | certified, published, promoted, per condition | required: production refuses to promote an uncalibrated generation |
| reranker | **OFF** | measured: cannot help, and hung. See below |
| sparse | default | measured identical to baseline |
| HNSW widening | default | measured identical to baseline |

**Retrieval is saturated on this corpus, and that is the finding that governs the rest.** Without
any reranker, `hit@1 = 20/20`: the correct source is already ranked FIRST for every answerable
query. `sparse=fts` and a 20x HNSW widening both measured identical to baseline. No retrieval
setting can raise a ceiling that is already reached.

⚠️ **The reranker is off for two independent reasons, and the second is operational.** It cannot
improve rank-1 retrieval that is already perfect; and the Voyage path builds
`FallbackReranker(primary=Voyage, fallback=local cross-encoder)` EAGERLY, which hung reproducibly
on VPS2 with the server idle at 0.3% CPU and every call timing out at 90 s. HuggingFace was
reachable (HTTP 200) so no root cause is claimed. A reranker that cannot help and does not reliably
start is not a configuration a public number should rest on. `RECALL_RETRIEVAL_PROFILE=quality` is
also NOT used: it is hard-wired to a pinned local cross-encoder and refuses to start without
`RECALL_RERANK_PATH` and a digest equal to `PINNED_RERANKER_SHA256`.

⚠️ **voyage-4 is chosen for representativeness, not because it measured better.** It certified at
separability **0.996 [0.977, 1.000]**, threshold 0.465, against fastembed's **1.000 [1.000,
1.000]** on the same corpus and query set. Both saturate retrieval. voyage-4 costs an API call per
query and measured slightly WORSE on the separation the abstention threshold is fitted to. It is
used because it is the configuration recall ships and would be judged on, and this paragraph exists
so no reader mistakes it for a tuned advantage.

## MemPalace's configuration

`mempalace==3.8.0`, its published stdio MCP server, ingest through its own `--mode convos` path for
Claude Code transcripts, one palace per namespace rebuilt on every ingest, 20 read and navigation
tools, its shipped skills. Recorded in `adapters/mempalace/VENDOR_REVIEW.md`, which invites its
maintainers to dispute every judgement call before a number exists.

⚠️ MemPalace's published headline (LongMemEval 96.6%, "raw" mode) is **not reachable through the
MCP surface**: `raw`/`aaak`/`rooms` are retrieval strategies inside their own benchmark script
(`build_palace_and_retrieve_*`), not settings on `mempalace-mcp`. Both products are measured
through their published MCP servers, which is the comparable thing, and neither is measured in its
own bespoke harness.

## Endpoints, in reporting order

1. ~~Net harm~~ — **structurally empty**. Interpretable on `TWO_SIDED` only, and no planted task is
   in that stratum. Reported as empty, never as zero.
2. **Damage rate**, `DAMAGE_ONLY`, per condition: paired cells where the arm failed what `bare`
   solved. 27 paired cells per arm per condition before discards.
3. **Abstention rate**, on `absent` and `contradictory`, a lower bound always.
4. **Wrong-fact-applied**: the deliverable embodies a planted convention. Needs no reference arm.

Search rate is reported per memory arm per condition; below 0.50 is NOT INTERPRETABLE.

## Predictions

House prior: I over-predict magnitudes by two to four times, and four of seven predictions in
record 011 landed. These are set low deliberately.

1. **Endpoint 3 moves off zero for `recall`, and that is this run's headline change.**
   `abstention-002` measured 0.000 across all 351 sessions with the trust gate relaxed. With a
   certified calibration and strict trust I predict `recall` abstains on **5% to 30%** of `absent`
   cells. Mechanism metric beside it: the share of `recall_search` responses carrying
   `abstained: true`, which I predict is HIGHER than the cell-level rate, because abstention is a
   flag the agent must then honour in prose and the detector reads prose.
2. **Search rate, not retrieval, is the binding constraint.** Retrieval measured `hit@1 = 20/20`,
   so I predict `recall`'s search rate stays between **0.50 and 0.85** and that its task success
   tracks search rate more closely than anything else. Falsified if success is flat across
   conditions whose search rates differ by more than 0.20.
3. **005's apparatus check fails again.** `claude_md` damage above 3% in at least one condition,
   because one discordant cell in 27 is 3.70% and the threshold cannot be passed at this grid size
   except by luck. If it holds, endpoint 2 is void again and no harm number is reported.
4. **Endpoint 4 stays small for both products**: at most **6 cells each** across the whole grid,
   and **0** on the memoryless arms. A firing on `bare`, `placebo`, `claude_md` or `protocol` voids
   endpoint 4 rather than lowering it.
5. **Neither product separates from the other on task success.** I predict the `recall` and
   `mempalace` success rates differ by **less than 10 points** on every condition, with the
   per-task cluster CI crossing zero. Nine tasks is not enough to resolve a small difference and I
   would rather say so now than discover it in the writing.
6. **Both memory arms cost multiples of the controls in input tokens.** `abstention-002` measured
   `recall` at 49k-68k against 12.5k-14.4k. I predict both products land above **3x** the control
   arms, and that neither beats `claude_md` on wins-per-Mtoken on any condition.
7. **Cost under $2.50** for 702 sessions plus voyage-4 embedding and query calls.

## Exclusion, truncation and restart rules

A cell is discarded unless every arm proves its treatment was applied, and every discard is
published with its reason. Retries are triggered by wiring only, never by outcome. If the budget
binds, truncate seeds in reverse order and never tasks, conditions or arms. A condition with fewer
than 8 admitted tasks is reported as underpowered rather than as a result.

**Restart is a supported operation for this run.** A condition that already has a complete
`admission.json` is skipped on re-run; a condition with a partial one is refused and must be
archived by hand, because silently resuming a partial condition is how cells vanish. The run is
launched detached (`setsid nohup`) so an interactive session ending cannot kill it; that happened
in `abstention-002` and cost 86 sessions.

## What would falsify this

- Prediction 1 falsified if `recall` still abstains on 0 of ~117 `absent` cells with a certified
  calibration and strict trust, which would mean the product's gate does not reach the agent's
  behaviour at all.
- Prediction 4 falsified by one detector firing on a memoryless arm.
- Prediction 5 falsified if either product beats the other by more than 10 points with a CI
  excluding zero, which would be a real result and the one worth publishing.
- The run is void if the corpus bytes differ across arms, if either product's write path is found
  to have mutated its store mid-run, or if `recall`'s Voyage fallback counter is non-zero, which
  would mean a blend of two rerankers was measured instead of one configuration.

<!-- results are appended below this line; everything above is frozen -->
