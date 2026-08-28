# Adversarial audit of agent-memory-bench

Date: 2026-08-28
Target: `C:\Users\gde00\Documents\agent-memory-bench`, branch `codex/model-freeze-pilot`, HEAD `8e16f5f`
Method: read-only. No benchmark, pilot, diagnostic or recording was executed. Every number below
comes from committed artifacts, committed source, `git log`, or arithmetic over
`results/*/records.final.jsonl`.
Stance: I read this as a hostile, technically competent reviewer from mem0, Zep, Supermemory or
Cognee whose job is to discredit it. Where a choice favours RE-call I say so, whether or not it was
intended to.

## The one-paragraph verdict

The methodology infrastructure here is better than almost anything in this field. The frozen-marker
discipline held byte-for-byte across every commit, the admission gate is a real idea, the
three-way reference gate and the four-way damage gate are the right gates, and the falsification
record (22 predictions, 15 falsified, all published) is genuinely rare. None of that survives
contact with the competitor comparison as currently designed, because the **treatment is not the
memory layer**. The RE-call arm receives 5,428 characters of behavioural coaching that no other arm
receives, 4.2 to 4.5 times the input tokens of every other arm, a corpus format that is a verbatim
document store rather than anything a write-path product would produce, a mechanism metric that
reads RE-call's own source filenames, and a harm suite that currently tests exactly one failure
condition, the one RE-call has both a product feature and an instruction paragraph for. Each of
those is individually defensible and individually documented somewhere. Together they are a
benchmark that a competitor can dismantle in a single blog post, and the dismantling would be
substantially correct.

Findings are ordered by how much damage a competitor does by raising them first.

---

# MUST FIX before any competitor comparison

## F1. The RE-call arm is given 5,428 characters of behavioural coaching that no other arm gets, and it was adopted after a null result

**This is the single strongest line of attack and it is worse than the framing in the brief.**

The adapter contract states the rule the benchmark broke:

> Adapters must be additive: every memory arm receives the same CLAUDE.md bundle as the
> `claude_md` baseline, byte for byte, plus **at most a one-line integration sentence at the TOP**

[harness/adapters/base.py:18](harness/adapters/base.py:18). `adapters/recall/adapter.py:14` repeats
it: "The one-line tool instruction goes at the TOP of the system prompt."

What actually ran in `pilot-002`, `pilot-003-deepseek`, `pilot-004-placebo` and every diagnostic
since is `--recall-instruction skill`: the full body of
[adapters/recall/skill.md](adapters/recall/skill.md), 5,428 characters after frontmatter stripping,
verified sha256 prefix `1fdc9e85a556c2cc`, injected above the static bundle by
[scripts/pilot.py:71](scripts/pilot.py:71). For scale, `fs_grep`'s equivalent nudge is **231
characters**, one sentence, exactly as the contract requires
([adapters/fs_grep/adapter.py:22](adapters/fs_grep/adapter.py:22)). `claude_md`, `placebo` and
`bare` get zero. So the instruction budget across arms is 5,428 / 231 / 0.

The content is the problem, not the length. Read what the skill actually teaches:

- "search before your first file edit or state-changing command in a task" (generic agent hygiene)
- "decompose the task into its operations, and search for each operation plus its failure"
  (generic query-formulation technique)
- "Two or three short searches with different words beat one long one" (generic)
- "Do not search once, find nothing, and conclude the project has no opinion" (generic, and a direct
  instruction against the `absent` condition's failure mode)
- "`superseded`: a claim that was retracted... **Do not act on a superseded hit**" (product-specific
  verdict semantics, and a direct instruction against the `superseded` condition's failure mode)

Only the last block is RE-call-specific. The rest is portable coaching that would help any
retrieval arm, and the skill says so about itself:

> the gain came from *searching at all*, not from better queries

[adapters/recall/skill.md:34](adapters/recall/skill.md:34).

Now the provenance, which is the part that reads worst:

1. `pilot-001` ran the frozen one-liner. Primary endpoint **null**: `+0.0139`, CI
   `[-0.0278, +0.0556]`, McNemar p = 1.0. Search rate 0.211
   ([preregistration/000-pilot.md](preregistration/000-pilot.md), results section).
2. The committed decision gate said the remedy class was "instruction/skill/model, not tasks", so
   the change was preregistered rather than fished. Credit where due.
3. `pilot-002` swapped in the shipped skill. Search rate 0.211 to 0.806. Primary delta `+0.0139`
   to **`+0.2361`**.
4. Every headline since is measured against that treatment. `pilot-003-deepseek` `+0.2222`;
   `pilot-004-placebo` `+0.1736`.

A competitor's sentence writes itself: *the null result was fixed by adding a prompt, only to their
own arm, and the prompt is mostly generic advice that would have moved any arm.*

**Verdict: real flaw.** The instruction is a treatment, it is confounded with the memory layer, and
the harness cannot currently separate them.

**Remedy, and it needs all four parts:**

1. Split the skill into a **portable memory-use protocol** (search before acting, search by
   operation and symptom, two or three short queries, do not conclude silence from one miss, do not
   treat memory as authoritative over the code) and a **vendor result-schema appendix** (how to
   read this product's verdicts). The portable half goes verbatim to every memory arm including
   `fs_grep`. The appendix is per-vendor and length-capped, and every vendor gets to write theirs.
2. Add an arm that isolates it: `claude_md` plus the portable protocol, with no memory layer. If
   that arm moves, the current headline is partly prompt engineering and you want to have measured
   it yourself rather than have a competitor measure it.
3. Publish the instruction character count per arm in `environment.json` and in every results table,
   beside the success rate.
4. Amend [harness/adapters/base.py:18](harness/adapters/base.py:18) so the stated contract matches
   what is run. Right now the codebase documents a rule its own headline runs violate, which is the
   worst of both worlds: the reviewer finds the violation *and* the confession.

## F2. The benchmark measures only the read path, over a corpus shaped like RE-call's own store

`corpus/sessions/*.jsonl` is 24 verbatim recorded transcripts plus 99 distractors, bulk ingested
once before the grid, never written to again. `harness/transcripts.py` renders each to markdown and
every arm indexes the same bytes. That is scrupulously neutral **at the byte level** and
structurally biased **at the architecture level**:

- RE-call's value proposition is retrieval over indexed source documents. This design tests exactly
  that, at exactly its best: one governing fact, stated once, in a single high-signal authored
  paragraph (`followup.txt`), in one document out of 123.
- mem0, Zep and Cognee sell **extraction and consolidation at write time**. This design gives them
  zero credit for it and full exposure to its lossiness. Every fact they drop during extraction is
  an unrecoverable loss; every fact RE-call keeps verbatim stays retrievable.
- There is no task anywhere in the suite that requires synthesis across sessions, temporal
  consolidation, entity linking, or anything a graph memory exists for. Thirty tasks, thirty single
  discrete facts, each in exactly one document.

Preregistration 006 states this plainly and it is the most honest paragraph in the repository:

> `corpus/` is 125 pre-authored transcripts, bulk ingested... The agent never forms a memory from
> its own work, so **half of every product under test, the write path, is currently unmeasured**

[preregistration/006-longitudinal-suite.md](preregistration/006-longitudinal-suite.md). That
document is a DRAFT-status record with no results, and `README.md` says none of it.

**Verdict: real, and structural.** It is not fixable by disclosure alone, though disclosure is the
minimum.

**Remedy:**

1. Move the write-path admission into `README.md`'s Status section, in the same font as the arm
   roster. A reader should not have to open preregistration 006 to learn that half of every product
   is unmeasured.
2. Do not publish a multi-product ranking until the longitudinal suite has run. A ranking of memory
   products on read-only bulk ingest is a ranking of retrieval engines, and it should be titled that
   way if it ships first.
3. Add at least three tasks whose governing fact is **distributed**: two sessions that must be
   combined, or a fact that evolved across three dated sessions. A suite where consolidation can
   never win is a suite that cannot detect a consolidation product working.
4. Answering the brief's question 1 directly: yes, a competitor can claim the task suite favours
   retrieval over summarisation, and on this evidence they would be right. The single discrete
   governing fact is the mechanism.

## F3. The harm suite currently tests exactly one condition, and it is the one RE-call has both a feature and a coaching paragraph for

Preregistration 005 defines four corpus conditions and predicts `adjacent` will be the worst:

> **`adjacent` produces the most damage of the four conditions.** ... Damage rate for `recall` on
> `adjacent`: **10% to 25%** of paired cells

Measured against the repository as it stands:

| condition | tasks with a plant | plants recorded into the corpus |
|---|---:|---:|
| `absent` | n/a by design | n/a |
| `superseded` | 12 | **2** (`ts-base36-id`, `ts-tz-utc`) |
| `contradictory` | **0** | 0 |
| `adjacent` | **0** | 0 |

Every one of the 12 `plants.json` files declares `superseded` and nothing else. Every one of the 12
`damage.py` detectors opens with a guard returning False for any condition that is not
`superseded`. So the only harm condition the apparatus can currently measure is:

- the one RE-call's search result schema natively models (`superseded_by`, `valid_until`,
  `valid_from` are fields in the live tool output), and
- the one the RE-call arm alone is explicitly coached on, in
  [adapters/recall/skill.md:78](adapters/recall/skill.md:78): "Do not act on a superseded hit."

Meanwhile `absent` and `contradictory` map onto the skill's other paragraphs ("Treat that as no
answer, not as a weak yes", "Do not search once, find nothing, and conclude the project has no
opinion"), and `adjacent`, the one condition with no coaching and the one predicted to do the most
damage, has no plants at all.

I accept that this is work in progress: the plant commits are from the last two days and a recording
batch may still be running. That is exactly why it belongs at the top of a must-fix list rather than
in a footnote. If the abstention suite runs and publishes in its current shape, the finding is not
"incomplete", it is "the harm suite was scoped to the failure mode the sponsor's product handles".

**Verdict: real, and currently unintentional. It will not read as unintentional.**

**Remedy:** do not run or publish the abstention suite until `adjacent` and `contradictory` have
plants on at least 8 `DAMAGE_ONLY` tasks each, or publish it explicitly retitled as a *supersession*
suite with 005's prediction 1 marked unevaluated and the reason stated. And strip the
condition-specific coaching out of whatever instruction the memory arms carry, per F1: an arm told
in advance how to handle superseded hits is not being tested on superseded hits.

## F4. The governing-memory metric is a filename substring match, and it gates model eligibility

The mechanism metric asks whether the string `sessions__` plus the task id plus `__` appears
anywhere in the retrieved contexts or in an MCP tool call's output
([scripts/analyze_pilot.py:90](scripts/analyze_pilot.py:90) and
[scripts/analyze_pilot.py:138](scripts/analyze_pilot.py:138)).

That string is the name `harness/transcripts.py` gives a rendered corpus file
([harness/transcripts.py:54](harness/transcripts.py:54)). I confirmed against a live stream that
RE-call returns it verbatim in every hit, as `"source": "sessions__ts-stable-sort__p01.md"`.

So `reached` measures "the product returned a result carrying our source filename". Consequences:

- **A product that returns extracted facts rather than source documents scores 0 by construction**,
  with perfect retrieval. mem0 returns memories, not file paths. Zep returns graph nodes.
- That is not merely a reporting problem. Preregistration 002's frozen eligibility rule is "recall
  search rate at least 0.50, and **reached-given-searched at least 0.50**". Applied unchanged to a
  competitor arm, that rule disqualifies an extraction product for a reason that has nothing to do
  with retrieval quality.
- Secondarily, the task id is in the filename and the filename is shown to the model. No stream in
  the 648 I scanned exploited it, but it is a lexical shortcut that rewards products which surface
  provenance strings.

**Verdict: real flaw, and it is armed. It sits inside a frozen selection rule.**

**Remedy:** redefine `reached` as content-based rather than path-based: does any retrieved text
contain a task-specific evidence n-gram drawn from the governing turn, using the same `fact_terms`
the leakage audit already maintains, or a hash of the `followup.txt` sentence. Fall back to path
matching only where a product supplies a path. Then write a new preregistration for the eligibility
rule; do not apply the old one to arms it was not written for.

## F5. The RE-call arm gets 4.2 to 4.5 times the input tokens of every other arm, and no arm is budget-matched

Computed over admitted cells:

| run | arm | mean input tokens | mean output | mean turns | mean wall (s) |
|---|---|---:|---:|---:|---:|
| pilot-003-deepseek | bare | 16,485 | 1,727 | 7.8 | 43.5 |
| pilot-003-deepseek | claude_md | 17,262 | 1,813 | 7.9 | 40.8 |
| pilot-003-deepseek | **recall** | **74,307** | 2,494 | 10.0 | 71.1 |
| pilot-004-placebo | bare | 18,905 | 1,801 | 8.1 | 50.2 |
| pilot-004-placebo | placebo | 17,364 | 1,767 | 8.0 | 49.8 |
| pilot-004-placebo | claude_md | 17,037 | 1,701 | 8.1 | 46.8 |
| pilot-004-placebo | **recall** | **76,556** | 2,669 | 10.1 | **123.7** |

Run totals from `results/pilot-004-placebo/costs.json`: recall 5,073,594 input tokens against
`claude_md`'s 1,196,113. Fresh (uncached) tokens: 24,123 against 7,298 per session.

Success per million input tokens: bare 21.8, placebo 27.4, `claude_md` 25.2, **recall 8.1**.

The placebo arm controls for the *static bundle's* length. Nothing controls for the 57,000 extra
runtime input tokens, the 2.2 extra turns, or the 2.6x wall time.
`reports/pilot-004-placebo-report.md` does note that "the task-success gain therefore needs to be
evaluated alongside cost and latency", which is honest, but a note is not a control arm.

**Verdict: disclosed, uncontrolled, and a competitor will run the control for you.** The obvious
counter-experiment is `claude_md` at a comparable budget: more turns, a mandatory re-read pass, or
simply a better model at the same spend. If that closes half the gap, the headline is partly "we
spent four times the tokens".

**Remedy:** add a compute-matched control arm to the competitor preregistration, and report
success per 100k input tokens as a co-primary alongside success rate. It also happens to be the
number a buyer actually wants.

## F6. The adapter layer is not the measured path, and four of the eight advertised arms do not exist

`README.md:44` lists eight arms. Reality:

| arm | adapter code | ever run in a measured comparison |
|---|---|---|
| `bare` | yes | yes |
| `claude_md` | yes | yes |
| `recall` | yes | yes |
| `placebo` | in `harness/placebo.py` | yes |
| `fs_grep` | yes | **no**, one 4-session smoke on one non-`ts` task |
| `mem0` | a docstring, and no `adapter.py` | no |
| `supermemory` | same | no |
| `zep` | same | no |
| `cognee` | same | no |

Worse, the two runners that produced every published number do not use the adapter layer in the
arm-critical path. `scripts/pilot.py` reimplements bundle construction
([scripts/pilot.py:84](scripts/pilot.py:84)), MCP config writing
([scripts/pilot.py:103](scripts/pilot.py:103)) and admission signals
([scripts/pilot.py:224](scripts/pilot.py:224)) inline, and `ARMS` at
[scripts/pilot.py:48](scripts/pilot.py:48) is a hardcoded four-tuple with no adapter lookup.
`scripts/diagnostic.py` does use adapters, but its `ARMS` at
[scripts/diagnostic.py:40](scripts/diagnostic.py:40) has **no `bare` arm**, which preregistration
005 declares mandatory.

And `fs_grep`'s sandbox overlay, without which the arm has no memory, exists only in
`scripts/smoke.py` ([scripts/smoke.py:139](scripts/smoke.py:139)). The adapter's own comment says
"The sandbox builder overlays this directory"
([adapters/fs_grep/adapter.py:81](adapters/fs_grep/adapter.py:81)); `harness/sandbox.py` contains no
such code.

Consequences a competitor will name:

- The vendor-review promise (`README.md:23`) is a promise to review code that the measured runs do
  not execute. **No `adapters/*/VENDOR_REVIEW.md` exists for any adapter, including `recall`.**
- **No `adapters/*/versions.lock` exists**, and `adapters/recall/config.frozen.json:11` reads
  `"package_pin": "TBD: recall-rag==<exact version, frozen at the Phase 4 preregistration>"`. The
  only arm ever measured has an unpinned version.
- `fs_grep` is the baseline the README itself calls the field's most damaging result ("If this
  benchmark omitted that baseline, Letta would run it for us"). It has never appeared in a measured
  comparison, and neither runner can currently run it.

**Verdict: real, and it undercuts the neutrality claim at its root.** The neutrality argument is
"RE-call is provably just another adapter" (`adapters/recall/adapter.py:5`). It is not another
adapter; it is the only one wired into the measurement path.

**Remedy:** make `scripts/pilot.py` construct every arm through `AdapterRegistry`, move the
`sandbox_overlay` handling into `harness/sandbox.py`, add `bare` to `diagnostic.py`, run `fs_grep`
in the next measured grid whatever else happens, and either build the four competitor adapters or
remove them from the README's arm list until they exist.

## F7. Nothing here is reproducible by a third party

Answering the brief's question 7 directly: **no**, and by a wider margin than the missing Docker
service.

1. **The RE-call version is unknown.** `package_pin` is `TBD`. `scripts/pilot.py`'s own docstring
   says `PYTHONPATH` must be "pinned to the recall checkout that serves the MCP server", so every
   published number was produced against an unspecified local worktree. Nobody can rerun the arm at
   the version that produced the result.
2. **The results behind most appended conclusions are untracked.** Committed: `pilot-001`,
   `pilot-002`, `pilot-002-repair`, `pilot-003-deepseek`, `pilot-003-gpt53`, `smoke-002`. Untracked:
   `pilot-004-placebo`, `resolution-001`, `midband-001`, `diagnostic-009`, `diagnostic-010`, and
   every other diagnostic. Those untracked runs are the evidence for preregistration 004's results,
   007's and 009's strata, `reports/pilot-004-placebo-report.md`, and the "what I already know"
   sections of 005 and 006.
3. **The screen silently degrades when they are missing.**
   [scripts/select_abstention_tasks.py:81](scripts/select_abstention_tasks.py:81) skips a run whose
   `records.final.jsonl` is absent. A fresh clone has no `results/resolution-001/`, so the
   stratification that decides the abstention suite's task set returns a different answer with no
   error. `tests/test_recall_instruction.py:46` similarly skips when
   `results/pilot-004-placebo/environment.json` is absent.
4. **Docker cannot stand the arm up.** `docker/compose.yaml` provides a `pgvector` container with no
   migration step and a harness image whose `CMD` is `pytest`. There is no `pip install recall-rag`,
   no MCP server service, no corpus ingestion step. "One-command reproduction" is aspirational.
5. `results/*/cfg/` is gitignored, so the exact per-task system prompt each arm received is not in
   the repository, only its sha256 in `environment.json`.

**Credit where it is due:** for the tracked runs, all 216 raw gzipped streams per run are committed.
That is far more than most published benchmarks ship, and it is what let me verify several claims
above independently.

**Remedy:** pin `recall-rag` to a released version and rerun at least one grid at that pin before
publishing anything competitive; commit `results/pilot-004-placebo`, `resolution-001` and
`midband-001`, or state in each preregistration that the evidence is unpublished; make
`select_abstention_tasks.py` raise on a missing run rather than continue; finish the compose file.

## F8. The sandbox lives inside the benchmark repository, a few directories below `oracles/`

`scripts/pilot.py:302` puts each session's working directory at
`results/<run>/work/<task>/s<seed>/<arm>`. The agent has unrestricted `Bash`
([scripts/pilot.py:50](scripts/pilot.py:50)) under `--permission-mode acceptEdits`, and it knows its
absolute path: `system/init` carries the full path and every tool result repeats it.

Six directories up sit `oracles/<task>/expected_next.txt`, `tasks/<task>/reference/informed.py`,
`tasks/<task>/checker.py` and the entire `corpus/`. Nothing in the harness prevents a session from
reading them.

**What I checked:** I scanned all 648 committed streams from `pilot-001`, `pilot-002`,
`pilot-003-deepseek` and `pilot-003-gpt53` for references to `oracles/`, parent-directory walks,
`reference/informed`, `reference/naive`, `checker.py`, `expected_next`, `expected_archive`,
`expected_app`, `expected_gitignore`, `corpus/sessions` and `/tasks/ts-`. **Zero hits.** The only
`agent-memory-bench` occurrences are the sandbox's own path. So it has never happened.

One accidental mitigation is worth recording because it is load-bearing and undocumented:
`sandbox.restore` runs `git init` inside the sandbox
([harness/sandbox.py:97](harness/sandbox.py:97)), so when an agent ran
`git rev-parse --show-toplevel` in `pilot-003` it got the sandbox, not the benchmark repository.

**Verdict: not exercised, but unmitigated, and it will be exercised eventually.** A stronger model, a
longer timeout or a frustrated agent is all it takes. In a competitor comparison the accusation
writes itself the moment one arm's success rate looks anomalous.

**Remedy:** put sandboxes in a temp root outside the repository (`sandbox.WORKSPACES` already
parameterises the fixture root; the destination is chosen by each runner), and add a stream scan for
oracle-path access to the admission gate as a hard discard reason. The scan I wrote takes four
seconds over 648 streams and could run in CI over every published run.

---

# SHOULD DISCLOSE

## F9. `claude_md` is a fixture README, not static memory, and on one task it actively misdirects

The designated baseline's bundle is built by [scripts/pilot.py:84](scripts/pilot.py:84): two lines of
`GENERIC_RULES` ([scripts/pilot.py:56](scripts/pilot.py:56)) plus `tasks/<id>/tree/README.md`, which
is typically three to five lines of orientation. The repository calls this "the realistic incumbent,
because nobody runs Claude Code memory-free"
([adapters/claude_md/adapter.py:3](adapters/claude_md/adapter.py:3), `README.md:29`).

It is not an incumbent. A real project `CLAUDE.md` is a curated conventions file, and it is exactly
where a team would write "order ids use a restricted alphabet". The audit
([scripts/audit_corpus.py](scripts/audit_corpus.py)) guarantees the governing fact is absent from it.
So `claude_md` is a **floor with a document attached**, and the primary contrast is "has the fact"
against "provably does not have the fact".

Worse, on `ts-legacy-hash` the README actively instructs the wrong thing:

> For digests of resource ids use `hashutil.fast_hash`; it is the fast-path helper.

while the governing fact is that `fast_hash` collides. Measured outcome, both runs:

| task | pilot-003 bare / claude_md | pilot-004 bare / claude_md |
|---|---|---|
| ts-legacy-hash | **1.00 / 0.00** | **1.00 / 0.00** |
| ts-golden-regen | 0.33 / 0.00 | 0.67 / 0.00 |

That is a reproducible, total destruction of the baseline by its own bundle. It is a legitimate task
design (the document is stale, memory holds the correction) and it explains a large part of why
`claude_md` scored *below* `bare` in `pilot-003` (36.1% against 50.0%). It is not compatible with
describing `claude_md` as the realistic incumbent.

It also lands on preregistration 002's frozen model-selection rule: "select the model with the higher
`claude_md` success rate". That rule was written to avoid selecting on the memory delta, which is
right, but it selects on a baseline that one task's fixture is designed to defeat.

**Verdict: defensible design, indefensible framing.**

**Remedy:** rename the arm's description from "the hand-written static bundle / realistic incumbent"
to what it is, "fixture orientation README", in `README.md`, `adapters/claude_md/adapter.py` and every
results table. Consider adding a genuine `curated_claude_md` arm: a hand-written conventions file that
contains some of the governing facts and not others. That is the incumbent, and it is the arm a buyer
actually compares against.

## F10. Every discard in the fact-present runs was caused by the RE-call arm, and pilot-002's published analysis pools a RE-call-only re-roll

From `admission.json` across the runs:

| run | discarded cells | attributed to |
|---|---:|---|
| pilot-003-deepseek | 0 | n/a |
| pilot-004-placebo | 9 | recall 9 (8 MCP failed, 1 API), placebo 1 |
| pilot-002 | 10 | **recall 10** |
| pilot-003-gpt53 | 32 | HTTP 402 across all arms |

Structurally, only an MCP arm can fail to be wired. `bare`, `claude_md` and `placebo` have no
equivalent failure mode. So the discard rule protects exactly one arm's worst outcome, and the
published rate is conditional on RE-call's server having started.

`scripts/discard_sensitivity.py` exists and says this in its own docstring, and
`reports/pilot-004-placebo-report.md:208` publishes the intention-to-treat column. **That is
excellent and it is the right response.** Two things it does not cover:

1. **pilot-002's discards were not a transient.** They were `ts-retry-cap` seed 2 plus **all three
   seeds of `ts-semver-pin`, `ts-stable-sort` and `ts-tz-utc`**: the last four tasks in alphabetical
   run order. Three whole tasks were removed from the tail of the run.
   `harness/memory_startup.py:7` argues, correctly for pilot-004, that a time-clustered failure is
   "uncorrelated with tasks"; for pilot-002 the fixed run order makes those the same thing.
2. **The pilot-002 repair re-rolled one arm's dice after seeing them lose.**
   `results/pilot-002/analysis.json` records `analysis_basis: "pilot-002 original records with ten
   infrastructure-discarded recall cells replaced by results/pilot-002-repair"`, with
   `"successes": 7` of 10. The RE-call arm's overall rate in that run is 0.639, so the repaired subset
   came back at 0.70. The `claude_md` sessions for those ten cells were **not** rerun, so 10 of 72
   cells (13.9%) pair a fresh RE-call session against a `claude_md` session from a different day and
   a different database state (migration `0015` was applied in between). The frozen text of
   preregistration 001 says a session error "discards the cell via the gate"; it does not
   preregister a repair-and-merge procedure, which was decided after the discards were seen.

**Verdict: the mechanism is principled; the pilot-002 application is a post-hoc analysis-basis change
that moved the headline up.**

**Remedy:** publish pilot-002 on both bases (62 admitted cells and 72 repaired) exactly as pilot-004
publishes per-protocol and intention-to-treat; write the repair rule into the competitor
preregistration before the run, including whether the paired arms are rerun together; and publish a
per-arm "treatment-application failure rate" beside every success rate, because for a buyer an 11.1%
server-startup failure rate is part of the product.

## F11. The retry is documented as wiring-only and retries timeouts

[harness/memory_startup.py:25](harness/memory_startup.py:25):

> A bounded retry, triggered by wiring alone. `infrastructure_failure` NEVER reads `record.success`,
> the checker verdict, or anything the model did.

But [harness/memory_startup.py:227](harness/memory_startup.py:227) returns a retryable reason
whenever `record.error` is set, and `record.error` includes
`ClaudeTranscriptError: claude exceeded timeout_s=600`, raised at
[harness/claude_exec.py:605](harness/claude_exec.py:605). A timeout is not a wiring fault. It is an
outcome, and it correlates with task difficulty and with session length. The RE-call arm's sessions
are 2.2 turns longer and up to 2.6x slower (F5), so it is the arm most exposed to the 600 second
ceiling and therefore the arm that draws the most extra attempts, up to three, on hard tasks.

The rule is symmetric in text and asymmetric in effect.

**Verdict: real, small in current data (no timeouts appear in the committed discard reasons), and it
will grow with a stronger model and more memory arms.**

**Remedy:** separate the two triggers. Retry on "the memory surface was absent" and on transport
errors; count a timeout as a task failure, or at minimum record `retry_reason` per attempt and
publish the counts per arm. And fix the docstring so it stops asserting something the code does not
do.

## F12. Statistical exposure: no multiplicity control, and between-run variance the CI does not capture

Three separate points.

**(a) No multiplicity adjustment exists anywhere.** I searched `preregistration/`, `reports/`,
`docs/`, `harness/` and `scripts/` for bonferroni, family-wise, multiple comparison, false discovery,
holm and multiplicity. Zero hits. Across ten preregistrations there are dozens of endpoints and
contrasts. Each record designates a primary and lists the rest "in reporting order", which is a
legitimate hierarchical structure, but it is never *named* as the multiplicity control, and the
published narratives quote p-values from secondary and exploratory contrasts (`bare` vs `claude_md`
p = 0.00195, placebo vs bare p = 0.219) without labelling them unadjusted.

**(b) The cluster bootstrap does not capture run-to-run variance, and you have the data to show how
much it misses.** `pilot-003-deepseek` and `pilot-004-placebo` ran the same protocol, model, tasks
and seeds. Per-task `recall` minus `claude_md` deltas across the two runs:

- Pearson r = **0.625** over 24 tasks
- mean absolute difference between the two runs' per-task deltas: **0.146**
- **5 of 24 tasks** flip sign or move by at least 0.50: `ts-atomic-write` +0.67 to 0.00,
  `ts-manifest-rel` +0.33 to **-0.33**, `ts-legacy-hash` +0.33 to 0.00, `ts-bom-merge` 0.00 to +0.50,
  `ts-base36-id` +0.33 to 0.00

The cluster bootstrap resamples tasks within one run and therefore treats each task's delta as
measured without error. It is not. The published CI half-widths (about 0.11 to 0.13) are of the same
order as the between-run instability of the quantity being resampled.

**(c) The effect is concentrated.** In `pilot-004-placebo`, **9 of 24 tasks** contribute a nonzero
delta and the top three carry 64% of the summed effect. In `pilot-003-deepseek`, 11 of 24 contribute
and the top three carry 38%. The headline "+17.4 points" reads as a broad improvement; it is a large
improvement on about 40% of the suite and exactly zero on the rest.

**Verdict: the implementations are correct.** I read `harness/stats.py`; the exact McNemar at
[harness/stats.py:100](harness/stats.py:100) is right, the degenerate-sample handling is unusually
careful, and the preregistration's own statement that McNemar over cells "overstates confidence" is
exactly right. **The exposure is in what is not reported.**

**Remedy:** state the hierarchical-testing structure explicitly in the competitor preregistration as
the multiplicity control, and pre-specify which contrasts are confirmatory; publish the two-run
per-task correlation above as a measured stability estimate beside every cluster CI; and publish
"tasks contributing a nonzero delta / total tasks" beside every headline.

Minor: [scripts/analyze_pilot.py:31](scripts/analyze_pilot.py:31) reimplements `cluster_bootstrap`
with `seed=42` while [harness/stats.py:73](harness/stats.py:73) uses `seed=12345` and a different
index clamp. Two implementations of the headline interval is one too many.

## F13. The frozen model is a single cheap flash model, and the only stronger candidate was never rerun

Every published result is `deepseek/deepseek-v4-flash`. The one attempt at `openai/gpt-5.3-codex`
failed the 95% admission rule on OpenRouter HTTP 402 credit errors (32 of 72 cells discarded) and has
not been rerun. Preregistration 002 reports this correctly and refuses to call it a model result.
Good.

The residual exposure is external validity, and it interacts with F1: a 5.4 KB behavioural instruction
moves a flash model a great deal (search rate 0.211 to 0.806). There is no evidence about whether it
moves a frontier model, or whether a frontier model needs a memory layer for these conventions at all.
`bare` at 46.3% pooled over 30 tasks at n = 12 is a weak-model floor.

**Remedy:** state in every publication that the result is for one cheap model. Rerun GPT-5.3 Codex
before any industry-benchmark claim, and treat "does the effect survive a stronger model" as a named
open question rather than a footnote.

## F14. Preregistration 009's apparatus clause: half the reasoning is sound and half has no power

The brief flagged this as the most likely place for rationalisation. It is, and here is the
arithmetic.

The frozen clause: "Prediction 3 falsified by any current `TWO_SIDED` task coming back at exactly 0
or 12 out of 12. The screen would then be measuring noise and **this record's own conclusions would
not stand**."

`ts-dedup-order` returned 12/12. The clause fired. The result section then argues via three
diagnostics that "the measurement is sound... the noise is in the RULE, not in the apparatus".

**The Fisher-test half of that defence has essentially no power.** I recomputed every comparison 009
cites, old measurement (n = 6) against new (n = 12), two-sided Fisher exact:

| task | old | new | p |
|---|---|---|---:|
| ts-bom-merge | 6/6 | 10/12 | 0.529 |
| ts-legacy-hash | 6/6 | 10/11 | 1.000 |
| ts-cli-exitcode | 0/6 | 1/12 | 1.000 |
| ts-dedup-order | 5/6 | 12/12 | 0.333 |
| ts-manifest-rel | 3/6 | 10/10 | **0.036** |

And the power check: starting from 6/6, the **first** new value that reaches p < 0.05 is **5/12**.
That is a true-rate collapse from about 1.0 to about 0.42. So "1 of 30 inconsistent, which is what
chance predicts at 30 tests" is a statement about a test that cannot detect anything short of a
catastrophic move. It is not evidence that the rates agree.

**The other half of the defence is genuinely sound and I want to say so clearly.** "21 of 30 tasks
returned the identical extreme" carries real information, because showing a hard extreme twice is
unlikely unless the true rate is near the extreme:

| true rate | P(6/6) | P(12/12) | P(both) |
|---:|---:|---:|---:|
| 0.99 | 0.941 | 0.886 | 0.835 |
| 0.95 | 0.735 | 0.540 | 0.397 |
| 0.90 | 0.531 | 0.282 | 0.150 |
| 0.85 | 0.377 | 0.142 | 0.054 |

Nine of eleven `DAMAGE_ONLY` tasks showing 6/6 and 12/12 is strong evidence their true rates are at
or above roughly 0.95. So "the extremes are stable, `DAMAGE_ONLY` rests on stable ground" holds.

**The rationalisation is the last step, and it is small but real.** The record says "Conclusions that
depend on exact membership at the boundary are unsafe, **and that includes the count of 7**", and then
fires the pre-committed stop rule, whose trigger is precisely the count of 7 against a threshold of 8.
If the count is unsafe, the inference from it is unsafe. What is defensible is the *decision* ("a
third attempt would be fishing"), not the *inference* ("the endpoint is permanently underpowered").
Those are different claims and the record runs them together.

**Verdict: mostly honest, one load-bearing overstatement, and one diagnostic that cannot do the work
asked of it.**

**Remedy:** append a correction under 009's marker, never editing above it, that (a) records the
Fisher power limit with the 6/6 to 5/12 figure, (b) separates the decision to stop from the inference
that the endpoint is underpowered, and (c) notes that a hard in-or-out rule at exactly 0 and 1 is the
wrong estimand for a screen whose purpose is statistical power. The right fix is not a third
measurement, it is to replace the boundary rule with a task weight proportional to `b(1 - b)`, the
information each task carries for the net-harm estimand. That is a rule change in the open, it uses
every task, and it makes the count-of-7 question disappear.

## F15. The damage detectors are exact-or-structural matchers, so the harm rate is a lower bound

Each `damage.py` fires only when the deliverable matches the planted outcome closely. `ts-tz-utc`
requires the produced archive and remainder to equal the damaged reference's line for line
([tasks/ts-tz-utc/damage.py:66](tasks/ts-tz-utc/damage.py:66)); `ts-ignore-gen` requires the new rule
first *and* the remaining rules byte-equal to the prior sorted content; `ts-append-only` requires a
single specific head line matching a regex.

An agent that retrieves the stale memo, applies it, and also slips somewhere unrelated is classified
`NEUTRAL_FAILURE`, not `DAMAGED`. Since the damage rate is the abstention suite's headline and it is
the number that counts against the memory layer, the measurement error is one-directional and in the
sponsor's favour.

The detectors already compute the information needed to say so: `ts-tz-utc` returns "archived N of
10, which is neither the correct split nor the planted one". `harness.damage.classify` throws that
away.

**Verdict: conservative by design, self-favouring in effect, and cheap to fix.**

**Remedy:** add a third bucket, `AMBIGUOUS_FAILURE`, for a failure that matches neither reference, and
publish it beside `DAMAGED` and `NEUTRAL_FAILURE`. Report damage as a band: exact-match as the floor,
exact-match plus ambiguous as the ceiling. The suite is then honest about an interval instead of
confident about a floor.

## F16. Two concrete holes in the substring leakage audits, beyond the semantic blindness they already document

Both `scripts/audit_corpus.py` and `scripts/audit_plants.py` state their substring limitation
explicitly and well ([scripts/audit_plants.py:41](scripts/audit_plants.py:41) is the best paragraph in
either file). Answering the brief's question about how much that matters: for *this* corpus, less than
it sounds, because the governing facts are highly specific phrases and the `bare` arm bounds
rediscovery empirically. Semantic leakage would show up as an inflated `bare` rate, and `bare` is
0.463 pooled over 30 tasks at n = 12. That is the right bound and it exists.

The two holes are mechanical, not semantic:

1. **`corpus/sessions/smoke/` is ingested but audited by neither script.** `CorpusManifest.build`
   globs `sessions/**/*.jsonl` ([harness/adapters/base.py:65](harness/adapters/base.py:65)), so the
   two smoke transcripts are in the manifest and in every arm's feed. Both audits build their
   "outside" set by iterating `discover_tasks()` and globbing `sessions/<task_id>/`
   ([scripts/audit_corpus.py:48](scripts/audit_corpus.py:48),
   [scripts/audit_plants.py:136](scripts/audit_plants.py:136)), and `smoke` is not a task id. So any
   term in those two files is invisible to the containment check. I found one live instance:
   `ts-empty-input`'s fact term `exit 0` appears in `corpus/sessions/smoke/s02.jsonl`. Low impact,
   correct diagnosis. `scripts/assemble_condition_corpus.py:126` has already been fixed for exactly
   this bug; the audits have not.
2. **The task prompt is not audited.** `task.json`'s `prompt` is the one piece of text every arm
   receives and no audit reads it. I checked all 30 by hand: only `ts-round-money` matches
   (`Decimal` inside "two decimal places"), which is a benign substring collision, not a leak. But
   the channel is unguarded, and the `fact_terms` lists are hand-written, so a future task can leak
   through it silently.

Also worth flagging: `salience_envelope` in `audit_plants.py` accepts any plant whose length falls
between the **minimum and maximum** of the real corpus and whose vocabulary novelty is below the
**most novel** real session. Those are the weakest possible bounds. A plant at the 99th percentile of
length passes while being far more salient than the median.

**Remedy:** include every `corpus/sessions/*/` directory in both audits' outside set, not just
discovered task ids; add `task.prompt` to the locus check; tighten the salience envelope to an
interquartile or 10th-to-90th-percentile band.

## F17. The cost ledger will report RE-call's ingestion as free and a competitor's as expensive

`harness/costs.py`'s docstring is exactly right about the hazard:

> Vendors report retrieval-side compression and quietly omit what their extraction pipeline spent at
> ingest time... Here ingestion tokens sit in the same table as session tokens

But `scripts/pilot.py:354` calls `summarize(records, pricing=pricing, model=args.model)` with **no
`IngestReport` rows at all**, so every published `costs.json` carries `"ingest_input_tokens": 0` for
every arm including RE-call. RE-call indexes with a local fastembed model, so it genuinely spends no
API tokens; mem0, Zep and Cognee run LLM extraction at ingest and will show large numbers against
RE-call's zero. That is a real product difference, but the ledger as it stands presents "local
embedding model" as "no cost".

There is also no accounting for RE-call's Postgres plus pgvector infrastructure, its indexing wall
time (recorded in `IngestReport.wall_time_ms`, never collected), or its 721-chunk corpus build.

**Remedy:** pass the `IngestReport` rows through in `pilot.py`; add explicit `ingest_local_compute`
fields (wall time, peak RSS, model name) so a zero in the token column is not read as a zero in the
cost column; and put a footnote in every cost table saying which arms pay at ingest in tokens and
which pay in local compute.

## F18. Two admission-gate guarantees are documented and not implemented

1. `README.md:38` lists "sandbox files digest-verified" among the gate's checks, and
   [harness/sandbox.py:9](harness/sandbox.py:9) says "`harness/gate.py` refuses a pair whose two arms
   did not start from the same digest". **`harness/gate.py` contains no reference to
   `sandbox_digest`.** It is recorded by both runners
   ([scripts/pilot.py:309](scripts/pilot.py:309),
   [scripts/diagnostic.py:451](scripts/diagnostic.py:451)) and compared by nothing.
2. [harness/adapters/base.py:161](harness/adapters/base.py:161) says `config_dir_digest` "is asserted
   stable across sessions of one run". No such assertion exists anywhere.

Neither has caused a problem, because `sandbox.restore` is deterministic. But a documented guarantee
that does not exist is worse than an absent one: a reviewer who finds it stops trusting the other
guarantees, all of which happen to be real.

**Remedy:** implement the cross-arm digest comparison in `admit_cells` (about eight lines: group by
cell, compare `metadata["sandbox_digest"]`, discard on mismatch), or delete both claims.

## F19. Everything is public, there is no held-out split, and a vendor can trivially detect the benchmark

The corpus, all 30 task fixtures, all checkers, all oracles and both reference solutions per task are
in a public repository. The vendor-review process invites each vendor to read their adapter config and
the corpus format before the run. There is no private task set and no held-out corpus.

A vendor can therefore:

- read all 24 governing facts and the exact oracle expectations before their arm runs;
- detect a benchmark session from the namespace, which is literally `smoke-recall-0`,
  `bench-recall-pilot`, `bench-recall-diag009`, taken from every `environment.json`;
- detect it from the corpus filenames, which carry the task id in every retrieved hit
  (`sessions__ts-stable-sort__p01.md`);
- tune ingestion or retrieval on the published corpus, deliberately or through ordinary iteration on
  a public benchmark.

The openness is a genuine virtue and I would not trade it away. But "vendor-reviewable before the run"
plus "no held-out split" is an unusual combination, and a competitor will point out that the sponsor's
own product was developed against this corpus while theirs was not.

**Remedy:** build a held-out set of 8 to 10 tasks with an unpublished corpus, run every arm on both,
and publish public-set and held-out-set numbers side by side. The gap between them is itself the most
interesting number the benchmark could produce. Also randomise namespaces per run so they carry no
"bench" or "smoke" token.

## F20. RE-call ran uncalibrated and trust-degraded in every published run, which is exactly the machinery the abstention suite is built to test

From a live `mcp__recall__recall_search` result in `results/pilot-003-deepseek`:
`"calibrated": false`, `"calibration_status": "missing"`, `"trust_state": "degraded"`,
`"failure_code": "INDEX_NOT_READY"`, `"verdict": "unverified"`, `"superseded_by": null`,
`"embedding_profile": "bge-small-symmetric-v1"`, `"index_generation": "legacy"`.

`adapters/recall/config.frozen.json:7` sets `"trust_mode": "development"`. So no abstention threshold
was fitted, every hit came back unverified, and supersession metadata was empty.

Two consequences pointing in opposite directions, and both should be stated:

- **In the benchmark's favour**: RE-call was not run in a specially tuned configuration. It ran on its
  default local embedder, uncalibrated, on the legacy retrieval path. Nobody can claim the arm was
  hand-optimised.
- **Against it**: RE-call's abstention and supersession verdicts are the features that would protect
  it on the `absent` and `superseded` conditions, and they were inactive. If the abstention suite runs
  in this configuration it measures a product with its differentiators switched off, and if it runs
  with them switched on it is no longer comparable to `pilot-003` and `pilot-004`.

**Remedy:** decide and preregister which configuration the competitor run uses, calibrate the tenant
before the run if the answer is "the shipped one", and record `trust_state` and `calibrated` per
session in the run artifact so the choice is visible in the data rather than only in a config file.

## F21. The placebo is a length control, not a placebo, and should not be called one

[harness/placebo.py:8](harness/placebo.py:8) draws from a nine-word vocabulary: `project records
contain general background material for routine review`, repeated to match the reference's
whitespace-token count and line count. The output is visibly degenerate. An agent reads one line and
knows the file is noise.

That makes it an honest **length** control, which is what preregistration 004 claims and what the
report says ("length-matched by whitespace tokens and lines, not hidden BPE tokens"). It is not a
control for "a project document is present and the model attends to it", because a detectable placebo
does not produce the attentional effect it is meant to control for. The null result (placebo minus
bare `+0.0556`, p = 0.219) is therefore consistent with "the model correctly ignored obvious junk"
and tells you very little about dilution.

Repeated vocabulary also compresses very differently under BPE than English prose, so the model-token
match is worse than the whitespace-token match suggests. The preregistration says actual input tokens
are a secondary audit; I could not find that audit published.

**Remedy:** keep the arm, keep the honest label, and stop describing the pilot-004 result as evidence
against context dilution. If dilution matters, the control is a length-matched *plausible* document
about an unrelated subsystem, which is also very close to preregistration 005's `adjacent` condition.

## F22. `oracle_memory` is a fair ceiling; `recall_prefetch` is confounded

Answering the brief's question directly.

**`oracle_memory` is fair.** `scripts/build_oracle_bundles.py:30` takes `users[-1]`, the authored
closing turn of the precursor session, and injects it into the system prompt with no retrieval at all.
That is the right ceiling: can the agent do the task when it is simply told the fact. RE-call cannot
exceed it, and no competitor is disadvantaged by it.

Two cosmetic problems worth fixing before a competitor sees them:

- The bundle is formatted in RE-call's verdict idiom: `Status: {validity}`, `Supersedes: {supersedes}`
  ([harness/memory_prompt.py:19](harness/memory_prompt.py:19)). The ceiling should not be written in
  one vendor's vocabulary. Rename to neutral labels.
- `harness/memory_bundles.py:14` names the forbidden markers, which is good, but the bundle is one
  item per task with `validity: "current"` hardcoded. Under the abstention suite's conditions the
  oracle needs a per-condition definition and does not have one yet.

**`recall_prefetch` is confounded.**
[adapters/recall_prefetch/adapter.py:149](adapters/recall_prefetch/adapter.py:149) builds its prompt
as memory text plus the static bundle, with **no instruction at all**, while the `recall` arm carries
the 5,428-character skill. So the diagnostic's "access gap" between `recall` and `recall_prefetch`
mixes two changes: proactive versus agent-initiated retrieval, and skill versus no instruction. It is
a diagnostic rather than a ranked arm, so this is a should-disclose rather than a must-fix, but any
conclusion drawn from that gap is not identified.

---

# ACCEPTABLE, and here is the defence

These are the things a competitor will probe and lose on. They are worth knowing you can defend.

**D1. The frozen-marker discipline actually held.** I reconstructed every version of all ten
preregistration records from `git log` and compared the text above the results marker byte for byte
across every commit that touched each file. **Zero frozen sections were ever modified.** Every result
was appended. Amendments were made by writing a new record (007 supersedes 005's screen; 009
supersedes 007's and 008's strata) with the older tables left standing and explicitly marked stale.
This is the strongest single thing about the project and it is verifiable in about ten seconds by
anyone.

**D2. "Available is the gate; used is a finding."** [harness/gate.py:19](harness/gate.py:19) draws the
right line and the code honours it: a memory layer that was present and never called produces a
`note`, not a discard ([harness/gate.py:315](harness/gate.py:315)). That single decision is what keeps
the benchmark from silently deleting the most interesting negative result it can produce.

**D3. The cross-arm contamination check is mechanical, not remembered.** `with_forbidden_prefixes`
computes each arm's forbidden set as the union of every other arm's prefixes and refuses a roster
where two arms claim the same prefix ([harness/gate.py:75](harness/gate.py:75)). The gate then checks
both tool *availability* and tool *calls*. That is the right design for eight arms.

**D4. The three-way reference gate and the four-way damage gate.** Every task proves in CI that a
do-nothing sandbox fails, `naive` fails and `informed` passes
([tests/test_references.py](tests/test_references.py)). Every damage detector proves it stays silent
on `informed`, stays silent on `naive`, fires on `damaged_<condition>`, and does not fire for the
wrong condition ([tests/test_damage_detection.py](tests/test_damage_detection.py)). The middle
assertion in each is the one that carries the metric, and both files say so and name the mutation
that would break it. I have not seen this done properly anywhere else.

**D5. Raw evidence is committed.** All 216 gzipped session streams per tracked run are in the
repository. That is what let me verify the sandbox-escape question, the token accounting and the
governing-memory metric independently rather than taking `analysis.json` on trust.

**D6. No sandbox escape has occurred.** 648 streams scanned, zero hits on any oracle, checker,
reference or corpus path. F8 is a risk, not an incident.

**D7. The statistics are implemented correctly.** Exact McNemar written out in the standard library so
the primary endpoint has no third-party dependency, verified against scipy values
([harness/stats.py:100](harness/stats.py:100)); `None` returned rather than a number the sample cannot
support; the degenerate all-agree case returns `None` rather than p = 1.0, with a comment explaining
why; clustering on task is the correct conservative choice for a repeated-measures design; and the
preregistration itself says the cell-level McNemar "overstates confidence". The exposure in F12 is
about reporting, not about the code.

**D8. The reporting record is unusually honest.** pilot-001's null is published in full with a
"falsified" column. `pilot-003-gpt53` is refused as a model result. `results/*-invalid-*` directories
are kept rather than deleted. Preregistration 007 opens by disclosing that its author had already seen
the outcome data. 22 predictions, 15 falsified, all standing. If a competitor attacks the project's
integrity generally rather than its design specifically, this is the answer.

**D9. Corpus timestamp remapping is disclosed** (`corpus/README.md:14`), applies identically to every
product, and is hashed in the manifest.

---

# Answers to the eight specific questions, in one place

1. **Could a competitor claim the task suite favours retrieval over summarisation?** Yes, and they
   would be right. Thirty tasks, thirty single discrete governing facts, each stated once in one
   document, bulk ingested and never updated. No task rewards consolidation, synthesis or temporal
   reasoning. See F2.
2. **Is `corpus/sessions/*.jsonl` neutral across products?** Byte-identical, yes. Architecturally
   neutral, no. It is a verbatim document store, which is RE-call's shape; the render even names files
   after the task id, and the mechanism metric then searches for that name (F4). See F2 and F4.
3. **Are preregistrations 005's and 006's product-neutrality clauses honoured by the code?** 006's is,
   so far as an unrun suite can be. 005's is not: the four conditions are neutral as written, but only
   `superseded` has been built, and the RE-call arm carries an instruction that coaches three of the
   four conditions' correct behaviours. The clause says "a reviewer must be able to read the four
   conditions without being able to tell which product they were written by"; the clause is fine and
   the apparatus is not yet. See F3 and F1.
4. **Does the harness give RE-call more retries, time, tokens or a softer admission path?**
   - Retries: yes, two ways. It is the only arm that can fail the MCP wiring check and draw up to
     three attempts for it (defensible), and the retry also fires on timeouts, which the RE-call arm
     is most exposed to (F11).
   - Time: no. Same 600 second budget, which RE-call spends more of.
   - Tokens: yes, 4.2 to 4.5x, uncontrolled (F5).
   - Admission: yes, structurally. It is the only arm with a failure mode that produces a discard
     rather than a scored loss, and 100% of pilot-002's and pilot-004's discards were its (F10).
5. **Is `--recall-instruction skill` fair?** No. See F1, which is the longest finding here for a
   reason. Fairness requires splitting the portable protocol from the vendor schema appendix, giving
   the portable half to every arm, letting each vendor write their own appendix under a length cap,
   and adding an instruction-only control arm.
6. **Are the statistics sound?** The implementations are, and are better than typical. The reporting
   has three gaps: no named multiplicity control across ten preregistrations, a cluster bootstrap that
   does not capture the between-run instability your own two replications measure (r = 0.625, 5 of 24
   tasks flipping), and a headline that does not say the effect lives on 9 to 11 of 24 tasks. See F12.
7. **Is it reproducible by a third party?** No. Unpinned RE-call version, most result artifacts
   untracked, a screen that silently degrades when they are missing, and a Docker compose that cannot
   stand up the arm. See F7.
8. **Can the benchmark be cheated?** Not currently, by anything I could find in the artifacts: no
   governing fact reaches the agent except through memory (I checked prompts, fixtures, `dirty/`
   overlays, bundles and 648 streams), no sandbox escape occurred, and the checkers all run held-out
   oracle inputs. The open routes are structural rather than exploited: the sandbox sits inside the
   repository with `oracles/` reachable by `Bash` (F8), the corpus and every oracle are public with no
   held-out split and namespaces that announce the benchmark (F19), and the governing-memory metric
   can be satisfied by surfacing source filenames (F4).

---

# The shortest path to a defensible competitor comparison

In priority order, and none of these is optional:

1. Split the skill; give the portable half to every memory arm; add the instruction-only control arm;
   publish per-arm instruction size. (F1)
2. Build `adjacent` and `contradictory` plants, or retitle the harm suite. (F3)
3. Make the governing-memory metric content-based and write a new eligibility preregistration. (F4)
4. Add a compute-matched control arm and report success per 100k input tokens as a co-primary. (F5)
5. Move sandboxes out of the repository. (F8)
6. Pin `recall-rag`, commit the missing result directories, finish compose. (F7)
7. Route every arm through `AdapterRegistry`; run `fs_grep` in the next grid. (F6)
8. Rename the `claude_md` arm to what it is, and consider adding a real curated-conventions arm. (F9)
9. State in `README.md` that the write path is unmeasured. (F2)
10. Build a held-out task set. (F19)

Items 1 through 5 decide whether the comparison is a benchmark or a marketing asset. Items 6 through
10 decide whether anyone can check.

---

# Appendix: what I did not check

- I did not run `pytest`, `scripts/audit_corpus.py`, `scripts/audit_plants.py` or
  `scripts/select_abstention_tasks.py`. Every claim about their behaviour is from reading the source,
  and every leakage claim is from my own independent scan over the same files.
- I did not verify the corpus manifest hashes against the files on disk.
- I did not read all 30 checkers line by line. I read `ts-base36-id`, `ts-tz-utc`, `ts-legacy-hash`,
  `ts-golden-regen`, `ts-round-money`, `ts-append-only`, `ts-glob-hidden`, `ts-ignore-gen` and
  `ts-schema-additive` in full. One narrow observation from that sample: `ts-base36-id`'s checker
  discriminates on a single alphabet transition (H to J), so any alphabet that merely excludes `I`
  passes, including Crockford base32. The `naive` reference still fails, so the gate holds, but the
  checker tests a weaker condition than the governing fact states.
- I did not inspect `results/*-invalid-*` beyond confirming they exist, are quarantined, and are
  excluded from every analysis basis.
- I did not review the DEV.to drafts or any external publication.

---

# Addendum, same day: what the fixes turned up

Written while implementing the remedies above. Three of these are new findings, and the first is
the one a competitor would have reached for.

## A1. The published mechanism figure is the loosest of three bounds, and they disagree by 2.5x

F4 said the `reached` metric was a filename match. Implementing the content-based replacement made
the size of the problem measurable. Re-scoring the published runs over the recall arm's searching
sessions:

| signal | what it asks | pilot-003-deepseek | pilot-004-placebo |
|---|---|---:|---:|
| `reached_by_path` (**published**) | did a result carry our source filename | 0.850 | 0.926 |
| `reached_by_content` (new primary) | did the retrieved text state the governing fact | **0.550** | **0.648** |
| `reached_by_evidence` (strict) | did it overlap the authored decision turn | 0.333 | 0.444 |

They differ because recall returns *chunks* of a rendered session: a chunk can carry the right
filename while containing a part of the conversation that never states the decision. "The right
document was touched" is not "the deciding sentence arrived". 18 of 60 searching sessions in
pilot-003 disagree between the two.

Consequences:

- A reader of "reached-given-searched 0.85" hears "the governing memo reached the agent 85% of the
  time". The defensible range is 0.33 to 0.85, point estimate 0.55.
- Preregistration 002's frozen eligibility rule is "reached-given-searched at least 0.50".
  DeepSeek clears it on two signals and **fails it on the third**. Any re-use of that rule must
  name which signal it means.
- This is independent of the competitor-neutrality problem in F4 and strictly worse: F4 said the
  metric would unfairly zero an extraction product. A1 says it also overstated the arm it was
  built for.

Fixed in `harness/reached.py`, which computes all three and names the bracket. `analysis.json`
now carries all three for every run.

## A2. The real corpus is clean under normalisation, and that is worth stating positively

A peer session found that `record_plant.py`'s fact-term gate was defeated by markdown: a planted
session containing "the \*first\* occurrence" and "first-occurrence deduplication" passed a
substring test for `first occurrence`. The obvious worry is that the same blindness let a fact leak
into the **real** corpus, which would invalidate published results rather than future ones.

It did not. Re-checking all 30 tasks' `fact_terms` against every session, distractor, plant, fixture
tree and task prompt, with the JSONL **decoded** (an escaped newline hides a phrase from any
whitespace normaliser) and then normalised, surfaces **zero** leaks the old byte-level test missed.
137 corpus files. The published fact-present results are not affected.

Three real defects were closed anyway, because the gate was passing for the wrong reason:

- `scripts/audit_corpus.py` still used `.lower()` substring matching. `audit_plants.py` had been
  hardened; the audit guarding the **real** corpus had not.
- Neither audit decoded the JSONL.
- Neither audit opened `corpus/sessions/smoke/`, which is in the manifest and therefore in every
  arm's feed, because both iterate discovered TASK ids and `smoke` is not one.
  `scripts/assemble_condition_corpus.py` had already been fixed for exactly this.

The hardened audit found four violations, all **over-generic fact terms** rather than governing-fact
leaks: `exit 0`, `mask`, and `Decimal` (which matched its own prompt's "two decimal places"). Fixed
by making the three terms distinctive, which is the documented remedy. Both audits now run in CI,
which they did not before.

## A3. One task pair encodes one convention; the outcomes do not follow it

The same peer found two *plants* encoding "newest first". Checking the 30 **real** tasks pairwise,
one pair stands out: `ts-golden-regen` and `ts-ignore-gen`, Jaccard 0.33 over content words,
sharing `hand`, `only`, `script`, `via`. Both say "this file is generated by a script; never
hand-edit it".

The independence worry does not survive the data. Their outcomes diverge sharply in every arm
(`bare` 0.53 against 1.00; `claude_md` 0.00 against 1.00), because the difficulty lives in the
specific mechanics rather than the shared abstraction. So: disclose it, do not restate the
statistics. `scripts/audit_corpus.py` now reports such pairs on every run so a future task cannot
silently duplicate a convention.

## A4. CI has been failing, or passing vacuously, since the mid-band tasks landed

Two defects in the same command, both pre-existing and both confirmed against a clean checkout:

1. `python scripts/diagnostic.py --dry-run` raised `ValueError: task 'ts-bool-env' references
   missing bundle`. The six mid-band tasks declare `memory_bundle_id` and have no precursor, so no
   oracle bundle was ever built for them, and `MemoryBundleCatalog.load` refuses the whole catalog.
2. `--dry-run` had **no early return**. It probed the live MCP server and then executed the whole
   grid. It only ever looked like a check because the CI runner has no `claude` binary, so every
   session failed fast and the script exited 0.

Both fixed: tasks without a bundle are excluded and named, and the dry run starts no server, runs
no session, and creates no directory. CI now also asserts the tree is unchanged afterwards.

## Status of the twenty-two findings

| Fixed in code | Documented, needs a decision | Needs work I must not do |
|---|---|---|
| F1 instruction fairness | F14 prereg 009 correction (append-only, author's own record) | F3 `adjacent`/`contradictory` plants (recording) |
| F4 mechanism metric | F19 held-out task set (design call) | F13 GPT-5.3 rerun (credit, measurement) |
| F6 adapters on the measured path | F7 pin `recall-rag`; commit or disclaim untracked results | F5 the budget-matched arm must actually be RUN |
| F8 sandboxes outside the repo | F9 a curated-conventions arm (new content) | |
| F11 retry no longer re-rolls timeouts | F12 multiplicity statement in the next preregistration | |
| F15 harm reported as a band | F21 stop calling the placebo evidence against dilution | |
| F16 audit hardening + CI | | |
| F17 cost ledger and efficiency | | |
| F18 sandbox digest actually compared | | |
| F22 neutral oracle labels | | |
| A1, A2, A3, A4 above | | |
