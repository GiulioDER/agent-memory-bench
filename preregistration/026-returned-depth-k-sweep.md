# 026: does returning 20 hits instead of 5 buy back the retrieval miss, and what does the extra dose cost?

Status: DRAFT until committed; a committed record is frozen above the results marker.

**Date:** 2026-09-01

Written before the instruction variant exists and before any session runs.

## Question

On the `superseded` and `contradictory` conditions, does raising the recall arm's returned hit count
`k` from 5 to 20 reduce the share of sessions in which **neither** plant reaches the agent, and by
how much does it raise the rival dose that this project has already measured to be harmful?

## Why this, and the code facts that make it cheap

`k` has never been varied. `adapters/recall/adapter.py` never sets it, so every published run used
the server default of **5**, and the arm's own notes discuss the reranker and the embedder without
mentioning depth at all.

Read at the pinned version, `recall-rag==0.11.0`:

- `recall_mcp/service.py:1040` clamps `k` to `[1, MAX_SEARCH_K]`, and `MAX_SEARCH_K = 50`
  (`recall_mcp/service.py:175`).
- `recall_mcp/service.py:1044` then applies `if profile.name != "legacy": k = min(k, profile.returned_k)`.
- **Every profile in `recall/profiles.py` has `returned_k=5`**, including `LEGACY_PROFILE`, and all
  four have `candidate_k=20`.

Two consequences, and the second is the reason this experiment is nearly free:

1. **`k` is client-raisable only under the `legacy` profile.** The arm sets neither
   `RECALL_RETRIEVAL_PROFILE` nor `RECALL_RERANK`, so `legacy` is what it resolves to and the clamp
   is skipped. Under `fast`, `quality` or `code` the agent could pass `k=20` and silently receive 5.
   **This is the run's central apparatus risk and is checked before any session, below.**
2. **recall already retrieves 20 candidates per leg and discards 15 before the agent sees
   anything.** Raising the returned count spends no additional retrieval and no additional
   embedding; it stops throwing away work that has already been paid for.

### What sizes both sides

`corpus-size-is-not-retrieval-difficulty`, measured on the scale-25 corpus this run uses:

| depth | voyage-4 |
|---|---:|
| hit@1 | **0.333** |
| hit@10 | **0.879** |

and the same memo states in terms that at 25x scale the right session is first only 33% of the time
and outside the top ten 12% of the time.

Against that, `official-002-two-sided-result`'s dose-response on `contradictory`:

| rivals retrieved | sessions | solved |
|---|---:|---:|
| none | 34 | **0.85** |
| one | 11 | 0.55 |
| both | 9 | **0.33** |

Monotonic. So depth is the one knob that moves the benefit term and the harm term in opposite
directions at the same time, and this project has the decomposition to price both from a single
grid. **That is the whole reason to run it: not to find out whether depth helps, but what depth
costs.**

## Arms and configs

| arm | adapter config sha256 | versions |
|---|---|---|
| `recall` (treatment and baseline) | `ae92863ce399c46766c5b9cc566bee6cf22e39a416c8f53af5892cb7f7220a6d` | `recall-rag[fastembed,mcp,voyage]==0.11.0`, `strict` trust, `voyage:voyage-4`, reranker OFF, `legacy` profile |
| `bare` | n/a | pairing baseline |

Repo at `bb25d34`. The adapter config, corpus, generation, embedder, trust mode and allow-list are
unchanged. **The only variable is the `k` the instruction tells the agent to pass.**

## Grid

- Corpus: **`bench-lineage-t0-superseded`** (no lineage, 4,911 documents, scale-25 haystack,
  generation already built, certified and promoted). No rebuild. This is the corpus the Tier 0
  control ran against, so the `k=5` baseline is a re-run of a measured configuration rather than a
  remembered number.
- Conditions: `superseded` (the 45% miss) and `contradictory` (the dose).
- Arms: `bare`, `recall`. Seeds: 5. Model: `deepseek/deepseek-v4-flash`. Timeout 600s.
- Two instruction variants: `skill` at the default `k` (baseline) and a new `depth` variant naming
  `k=20`.

⚠️ **The `depth` variant does not exist.** `scripts/pilot.py`'s `--memory-instruction` takes
`("oneliner", "skill", "protocol")`. Its content is frozen here: the `skill` instruction verbatim
plus one clause instructing the agent to pass `k=20` on every memory call. Nothing else moves.

## Endpoints, in reporting order

1. **Primary: neither-plant share.** Denominator: recall-arm `superseded` sessions that issued at
   least one memory call. Numerator: those in which no plant's fact terms reach the agent, by
   `harness.reached`'s content signal.
2. Plant-retrieval split (current only / both / neither), same denominator.
3. Task success on `superseded`, recall against bare, per-task cluster bootstrap CI.
4. **Rival dose on `contradictory`** (none / one / both) and damage rate, paired against bare.
5. Compliance: mean hits returned per memory call, and the share of calls passing `k=20`.
6. Retrieved-text tokens per session, and cost per admitted cell.

## Predictions

Deliberately low, per `i-over-predict-effect-magnitudes` at twelve of thirteen.

1. **Mechanism first: mean hits per memory call rises from 5.0 to between 12 and 20.** If this is
   flat the profile clamped it and nothing else in this record may be read. Probability the
   deployment is `legacy` and the raise takes effect: **0.85**.
2. **Neither-plant share falls from 0.45 to 0.34** (range 0.28 to 0.41). About a third of what the
   hit@1-to-hit@10 gap suggests, discounted because those figures come from the retrieval probe's
   authored queries, and the agent's queries are keyword bags averaging 7.1 words with a different
   score distribution. Probability it moves in the predicted direction: **0.80**.
3. **Task success on `superseded` rises by +3 points** (range -2 to +9). Probability the CI excludes
   zero: **0.20**. Registered as probably underpowered.
4. **The dose rises and it costs something.** Both-rivals share on `contradictory` rises by 0.10 to
   0.25, and `contradictory` task success falls by 3 to 10 points. Probability the dose rises at
   all: **0.75**. This is the term the experiment exists to price, and I am registering that I
   expect depth to be a real trade rather than a free win.
5. **Retrieved-text tokens per session rise by 2x to 3x**, not 4x, because hits are truncated and
   the fused candidate pool will not always fill 20 slots.

## The prediction I most expect to be wrong, stated now

**That the miss share falls and task success does not follow, because sessions move from *neither*
to *both* rather than to *current only*.**

The `superseded` decomposition solves at 1.00 for current-only and **0.56 for both plants**. Depth
is indiscriminate: the stale plant and the current plant share the task's identifiers, so ranks 6
through 20 are at least as likely to contain the stale one. Endpoint 2 exists precisely to catch
this, and I am registering it at probability **0.35**.

That outcome would not be a failure of the idea. It would be the finding that **depth and selection
are complements**, and it is the single result that would make preregistration 025's enforcement
lane worth more rather than less, because filtering is what converts a *both* into a *current only*.
If both records run, that is the interaction to look at first.

## What would falsify this

- **Mean hits per call stays at 5.** The profile clamped `k`. The run measures nothing and must be
  **cancelled and not reported**, not written up as a null. A run that cannot move its treatment is
  the `the-apparatus-fails-toward-a-finding` shape, and a null is the cheapest thing it can produce.
- **Neither-plant share unchanged.** Depth is not the binding constraint on agent-shaped queries,
  and the miss is a formulation problem, which is what 024 tests.
- **Miss falls and damage rises enough to cancel it.** `k` is not a free lever; recall needs
  selection rather than depth, and the answer is 025 or a reranker rather than a bigger result set.
- **Compliance below 0.50** on passing the parameter. The record is about prompt compliance.

## Exclusion and truncation rules

- The frozen admission gate applies unchanged; discards are counted and published prominently.
- Budget truncation removes **seeds, never tasks or conditions**. Order: seed 5, then seed 4, then
  `contradictory` in full. Removing `contradictory` voids prediction 4 rather than reporting it at
  reduced n, and a run reporting only the benefit side of a two-sided lever must say so in its first
  sentence.
- A cell whose MCP server did not answer is retried once, then discarded.

## Apparatus verification, before any session runs

1. **Read the profile off the server, do not infer it.** `recall_mcp` logs at startup
   `retrieval profile %s (candidates %d/leg, returns %d, ...)`. Confirm it says `legacy` and
   `returns 5`. This is the single check that decides whether the run is worth paying for.
2. **One live call returning more than 5 hits**, against the run's own tenant and generation, before
   the grid starts. A passing check on the log line is not a passing check on the response.
3. **The rendered `prompt.md` differs** from the `skill` variant's and names `k=20`. Assert on the
   written file, not on the config.
4. **The baseline is reproducible.** Recompute the `k=5` arm's neither-plant share from the existing
   `lineage-t0-superseded` records and confirm it matches the 0.45 quoted here before treating that
   number as the baseline.

## What I already know

- `corpus-size-is-not-retrieval-difficulty` (hit@1 0.333, hit@10 0.879 at 25x),
  `official-002-two-sided-result` (the dose-response), `recall-lineage-fields-are-unpopulated` (the
  45% miss and what it is worth), `lineage-tier-result-t0-vs-t2` (the t0 baseline).
- The reranker is OFF in this arm on the recorded grounds that hit@1 was 20/20, which was measured
  on the 195-document corpus. `corpus-size-is-not-retrieval-difficulty` retires that reasoning for
  the 4,911-document corpus. **Turning the reranker on is a separate lever and is deliberately NOT
  varied here**, because it and `k` would confound; it needs its own record, and first an
  engineering fix for the hang the arm's own notes record on the serving host.
- Closed lanes this must not re-open: memo rewriting, LLM query expansion, fusion-weight gating,
  threshold recalibration, per-write automatic search, declaring lineage, all three graph
  mechanisms.

## Confounds I can name now

- **`k` and candidate depth are not the same knob.** `candidate_k` stays at 20 per leg, so this
  measures returning more of an unchanged candidate pool, not searching deeper. A null here does not
  license a claim about a wider pool, which has separately been measured negative in recall's own
  store (547 candidates lost 0.0513 R@100).
- **Context length is a confound with retrieval.** 20 hits is a materially longer prompt, and a
  success change could come from context dilution rather than from what was retrieved. Endpoints 1
  and 2 separate them: dilution predicts success falls while the retrieval split improves.
- **The dose metric and the miss metric share a denominator family but not a condition**, so
  endpoint 4's n is roughly a third of the `present` condition's and its CI will be wide.
- The corpus feed changed on 2026-08-29; no number here may be differenced against `pilot-003` or
  `pilot-004`.

<!-- results are appended below this line; everything above is frozen -->
