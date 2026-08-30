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

## 🔁 Correction, appended before the first session: `protocol` is dropped, and why

**Five arms, not six: `bare`, `placebo`, `claude_md`, `recall`, `mempalace`. 630 sessions, not
702.**

The frozen text above lists `protocol` as an arm. That was a mistake I made recommending it, and
the runner refused it outright:

> the `protocol` arm is the instruction-only control for the shared memory protocol, so it is only
> meaningful with `--memory-instruction protocol`. With `skill` or `oneliner` it would carry a
> different instruction from the memory arms it exists to be compared against.

`protocol` is not an arm you can add alongside the others: selecting it forces the WHOLE grid onto
the equalised instruction, and this record specifies `--memory-instruction skill`, meaning each
product carries its own official integration, per preregistration 006. Equalising the text measures
a common denominator neither product ships, which is a useful ablation and is emphatically not the
product comparison this run exists to make.

So `protocol` becomes a separate, labelled ablation if it is wanted, and the official run keeps the
instruction each vendor actually ships. `placebo` stays: it needs no instruction variant and is the
control that separates "memory helped" from "any extra context helped".

Prediction 5 is unaffected. Predictions 3 and 4 now range over five arms rather than six, and
prediction 7's budget is if anything looser at 630 sessions.

## Grid as actually prepared, measured 2026-08-29

| condition | tasks | sessions in feed | chunks | sessions to run |
|---|---:|---:|---:|---:|
| absent | 11 | 184 | 951 | 165 |
| superseded | 10 | 205 | 1129 | 150 |
| contradictory | 10 | 205 | 1078 | 150 |
| adjacent | 11 | 195 | 1033 | 165 |

Each tenant serves a promoted generation whose published calibration certified, with the threshold
fitted on that generation (`threshold_was_measured_here: true`) against the same 46 held-out
queries in every condition. `RecallAdapter.ingest` verifies all of that at run time and refuses a
tenant whose recorded corpus fingerprint does not equal the corpus the run assembled; that refusal
was exercised deliberately against a mismatched tenant and fired.

## 🔁 Correction, appended before the first session: how the run is actually detached

The frozen text says the run is launched with `setsid nohup`. **Neither is available in Git Bash on
this host**, so the detachment is done with PowerShell's `Start-Process`, in
`scripts/launch_official.ps1`. The property that matters is the one the frozen text was reaching
for and it holds: the launched process is independent of the shell that started it, so an
interactive session ending cannot kill it, which is the failure that cost `abstention-002` 86
sessions. A PowerShell background *job* would not have this property, and is deliberately not used.

Two consequences worth recording, because both are load bearing and neither is obvious:

1. **A detached process inherits only what the launcher sets.** MemPalace's adapter requires
   `MEMPALACE_VENV` and `MEMPALACE_PALACE_ROOT` and never guesses either, so the launcher passes
   both explicitly and refuses to start if the venv, the palace root or `OPENROUTER_API_KEY` is
   missing. Omitting them would have failed the `mempalace` arm at its first cell while every
   other arm ran normally, which is the shape of failure this benchmark is least able to see.
2. **Restarting after a mid-condition stop takes one extra command, on purpose.** `--resume` skips
   a condition that wrote `admission.json` and REFUSES one that did not, because resuming a partial
   condition would mix two runs' sessions inside it. `scripts/archive_partial.py` moves such a
   condition, both its results directory and its temp work root, into `results/archive/` with a
   README saying it is not a result. Nothing is deleted: a partial condition is the only surviving
   trace of what an aborted attempt did.

## Readiness, measured 2026-08-29 before the first session

| check | result |
|---|---|
| recall corpora | four tenants, each serving a promoted generation with a certified published calibration |
| corpus identity | `ingest` verifies the fingerprint and refuses a mismatch; the refusal was exercised deliberately and fired |
| recall reranker | provably OFF: server startup reports `reranker False`, Voyage fallback events 0 |
| MemPalace | 3.8.0, server serves 44 tools with all 20 allow-listed present; ingest filed 26 drawers from 4 sessions in 7.1 s and retrieved the signal session |
| grid | dry run at 630 sessions, 165 / 150 / 150 / 165, five arms, clean |
| instruction | each product carries its own shipped skill: recall 5,430 bytes, MemPalace 4,325 bytes |
| suite | 587 passed, 4 skipped; `ruff check` clean |

## 🔁 Correction, appended before the first session: the whole run moves onto VPS2

The frozen text and the two corrections above describe a run driven from a Windows workstation,
with recall reached on VPS2 over SSH and MemPalace running locally. **Every arm now runs on VPS2**,
which is also where the corpus lives. The reason is operational: an interruption on the workstation
must not be able to stop a 630 session run, and detaching a process there still leaves the run
hostage to that machine.

**What this changes about the measurement, stated plainly so a reader can judge it.**

recall's frozen config moves from `transport: ssh` to `transport: host`. The command string that
starts its MCP server is byte identical on either transport; only its carrier differs, a local
shell instead of `ssh`. The pinned interpreter is still named in it, strict trust is still
expressed by unsetting `RECALL_TRUST_MODE`, and the generation verification and row count run the
same SQL. This is not a retrieval setting and cannot change what recall returns.

⚠️ **It removes an asymmetry that would otherwise have been in the published numbers, and the
asymmetry favoured MemPalace.** Under SSH, recall paid a network round trip on every tool call
while MemPalace answered in process. Latency is not one of the four endpoints, so this could not
have moved task success directly, but it could have reached the numbers through the 600 second
session timeout, and a timeout driven discard is not neutral between arms. Under `host` neither
product pays a hop. Discards remain published per condition with their reasons, so the check
survives either way.

**What is verified on VPS2 rather than assumed**, measured 2026-08-29:

| check | result |
|---|---|
| interpreter | Python 3.12.3 there against 3.14 here; the suite is **585 passed, 6 skipped** on VPS2 |
| Claude Code | 2.1.251, installed for this run; the harness spawns the real CLI per session |
| recall corpus | `absent` verified through the host transport: 951 rows, 184 sessions, fingerprint matched |
| recall server | up on the host transport, 20 tools served, all 8 allow listed present |
| MemPalace | 3.8.0, 44 tools with all 20 allow listed present, ingest and retrieval both exercised |

⚠️ **MemPalace embeds locally and VPS2 is not an idle machine.** Its ingest smoke took **69.5 s for
4 sessions** on VPS2 against **7.1 s** on the workstation, part model download and part a host
carrying load average 8.9 on 12 cores from live trading services. So the MemPalace arm's ingest is
materially slower in the official run than in any preflight, and the run is bounded by a systemd
scope (`MemoryMax=16G`, `MemorySwapMax=0`, `CPUQuota=500%`, `nice -n 10`) so that it is killed
rather than the host. No endpoint depends on wall clock, and cost is reported in tokens.

**One standing rule is relaxed for this run, deliberately and on the record.** The project rule is
never two embedding processes on the embedding host. recall's embedding is `voyage:voyage-4`, a
hosted API that consumes no local compute, so it does not contend. MemPalace's does, and is the
reason the scope above exists rather than being waived along with the rule.

The project itself is not pip installable (a flat layout defeats setuptools' package discovery), so
it runs from the repository root as `python -m`, exactly as it does on the workstation. That is a
pre existing condition, noted so a reader who tries `pip install -e .` is not surprised.

## 🔁 Correction, appended 2026-08-30: the packaging defect above is fixed

The paragraph immediately above says the project is not pip installable. That was true when it was
written and is no longer true: `[tool.setuptools.packages.find]` now scopes discovery to
`harness*`, `adapters*` and `scripts*`, and `pip install -e .` succeeds. The sentence is left
standing rather than edited, because a record of what was believed at the time is the thing this
document is for. Nothing about the run changes: the harness still executes as `python -m` from the
repository root, exactly as it did on the workstation and as it does on VPS2.

## Status, 2026-08-30: `official-001` ran, and is NOT reported as a result

The grid described above executed in full: 630 sessions, four conditions, five arms, 118 admitted
cells of 126, $1.6986. Every condition verifies from its own published evidence with
`scripts/verify_run.py`.

**No arm-level number from it is reported here, and none should be quoted.** A results section was
appended on 2026-08-30 and retracted the same day. The reason is not that the numbers were
unflattering. It is that the run measured the instrument rather than the products, and the
instrument was found to be unable to answer the question this record asks.

### What the run established about the grid

| | |
|---|---|
| tasks the memory-free arm solved in **every** admitted cell | **7 of 11** |
| cells with any headroom for a memory layer to win | **13 of 118** |
| `bare` success across the grid | **0.890** |

Seven of eleven tasks cannot measure benefit at all: there is nothing left for memory to win on
them, and every retrieval is downside risk. There is also **no condition in which the governing
fact is simply present and correct**. All four vary what is missing or misleading, so a product
that never searches takes zero damage across the entire suite and forfeits nothing.

**The suite therefore pays abstinence**, and any ranking drawn from it would reward the most
conservative product rather than the most useful one. That is a defect in the benchmark, and it
would misrepresent every arm, not only the one its authors own.

The cause is a task-selection criterion that conflicts with itself: the harm suite admits a task
if it can express all four plant conditions, and never requires that `bare` sometimes fail it.
Those are different properties, and optimising the first silently discarded the second.

### What happens to this record

This preregistration is **not** withdrawn and its predictions are **not** edited. It stands as
written, with this note recording that its grid could not test them. A future run against a
repaired grid gets its own record rather than reusing this one, because a prediction is only
meaningful against the instrument it was written for.

`official-001` joins `midband-001` and `resolution-001` as a calibration and diagnostic run: it
informs the design and is not written up as a finding. That is the same treatment those runs
already receive, for the same reason.
