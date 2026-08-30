# Instrument review, 2026-08-30

`official-001` ran a full 630-session grid and its results were retracted the same day, because the
run measured the benchmark rather than the products. This is what it found about the benchmark,
what is being changed, and what is deliberately not being changed yet.

Nothing here is a product claim. Every arm-level figure from `official-001` stays unpublished.

## 1. The instrument had almost no dynamic range

| | |
|---|---|
| admitted cells | 118 |
| cells where **every** arm succeeded | **90** |
| cells where **every** arm failed | 7 |
| cells with any disagreement | **21** |
| sessions carrying zero information | **485 of 590 (82.2%)** |
| tokens carrying zero information | **83.6%** |

An 8h51m run produced 21 cells of evidence. Every conclusion drawn from it, including the
clustering caveats, follows from that number rather than from 118.

## 2. Task selection chose the tasks that could not inform

`resolution-001` screened all 30 tasks with the memory-free arm alone, 12 seeds each. Banding
those by measured `bare` success, against which tasks the harm suite actually selected:

| band | `bare` | tasks | selected into the harm suite |
|---|---|---:|---:|
| DEAD | 1.00 | 9 | **9** |
| marginal | 0.83 | 3 | 0 |
| mid-band | 0.17 to 0.75 | 4 | 1 |
| TOO HARD | ≤ 0.08 | 14 | 1 |

**All nine tasks where the memory-free arm never fails were selected, and thirteen of the fourteen
where it always fails were not.** Damage is defined as failing what `bare` solved, so a DEAD task
can only ever record harm; benefit is solving what `bare` failed, which a DEAD task cannot express
at all. The suite was therefore incapable of measuring benefit before it started.

The cause is a selection rule that conflicts with itself: `selection_for` admits a task if it
declares plants for a condition, and never asks whether anyone could fail it. Plant expressiveness
and mid-band difficulty are different properties, and optimising the first silently discarded the
second. It is not a coincidence that they trade off: a convention simple enough to plant four clean
variants of is usually simple enough for a competent agent to guess.

⚠️ **The `naive/` reference did not catch this and structurally cannot.** CI asserts that the
hand-written naive file fails the checker. That tests the checker. Whether a real memory-free agent
produces anything like it is a different question, and `bare` answers it: on these tasks it does
not, and solves them another way 89% of the time.

## 3. The condition set pays abstinence

`absent`, `superseded`, `contradictory` and `adjacent` all vary how the evidence is **bad**. There
is no condition in which the governing fact is present and correct. Memory usefulness is a
detection problem with two axes, and only one is instrumented:

| | corpus **has** the answer | corpus **empty or misleading** |
|---|---|---|
| product engages | win (benefit) | loss (damage) |
| product abstains | **loss (missed)** | win (correct refusal) |

The "missed" cell cannot fire, so never searching takes zero damage and forfeits nothing.
Abstinence is a strictly dominant strategy, and any ranking drawn from this suite rewards the most
conservative product rather than the most useful one. That misrepresents every arm, not only the
one this project owns.

## 4. The corpus is too small to challenge retrieval

| corpus | chunks |
|---|---:|
| bench `absent` | 951 |
| bench `superseded` | 1,129 |
| bench `contradictory` | 1,078 |
| bench `adjacent` | 1,033 |
| this project's own production memory store, for comparison | 9,801 |

Retrieval is being tested against a corpus an order of magnitude smaller than a single real store.
`hit@1 = 20/20`, which was cited in preregistration 014 to justify disabling a reranker, is not
evidence that retrieval is solved; it is evidence that the corpus contains too few competitors for
ranking to matter.

**Corpus scale is the only lever that raises difficulty for the memory arms without moving
`bare`.** Every other lever moves the floor as well as the ceiling.

## 5. What is being changed now

**Retire tasks that no arm has ever failed.** Across every run in this repository plus
`official-001`:

| task | sessions | failures, all arms, all runs |
|---|---:|---:|
| `ts-glob-hidden` | 113 | **0** |
| `ts-bool-env` | 62 | **0** |
| `ts-csv-quote` | 54 | **0** |
| `ts-append-only` | 117 | 1 |

A task no arm has ever failed cannot record damage or benefit. It is spend. These are retired from
the harm suite by an explicit, dated list rather than by deleting their plants, so the decision is
reversible and the work is preserved.

`ts-append-only` is retired on the same basis with its single failure recorded, because one
failure in 117 sessions cannot separate two arms either.

## 6. What is NOT being changed yet, and why

These need their own preregistration before anything is measured, because each changes what a
number from this benchmark means:

- **A `present` condition**, in which the fact is in the corpus, correct and unambiguous, so that
  not searching can lose. This is the fix for section 3 and is the highest-value single change.
- **Admission on measured difficulty.** A task should enter a suite on a measured `bare` band, not
  on whether it declares plants. The screening data already exists (`resolution-001`) and one
  `bare`-only pass over a task library costs about a fifth of a full grid.
- **Corpus growth of 10x to 50x** with realistic distractors.
- **A composite that reports both axes**, sensitivity on `present` and specificity on the
  adversarial conditions, so that a product which never searches scores zero rather than winning,
  and one that always trusts also scores zero.

## 7. The finding that reframes everything above

On the fourteen tasks where `bare` and `claude_md` both score approximately zero, a memory arm
converts impossible tasks into solved ones. Measured across the earlier pilots and the diagnostic:

| task | `bare` | `claude_md` | memory arm |
|---|---:|---:|---:|
| `ts-nfc-count` | 0/6 | 0/9 | **8/9** |
| `ts-round-money` | 0/6 | 0/9 | **6/9** |
| `ts-quote-shell` | 0/6 | 0/9 | **5/9** |
| `ts-stable-sort` | 0/6 | 0/9 | **4/9** |
| `ts-crlf-export` | 0/6 | 0/9 | **3/9** |
| `ts-base36-id` | 0/6 | 0/9 | 1/9 |

**None of these tasks was in `official-001`.** The benefit this benchmark exists to measure is
demonstrable and was excluded by the selection rule in section 2. That is the strongest argument
for the redesign and the clearest evidence that `official-001`'s retraction was correct rather
than convenient.

⚠️ These figures come from runs on a different instruction variant and are **not** a result. They
are the reason to build the `present` condition, not a substitute for it.

## 8. Appended 2026-08-30: two tasks encode one convention, and it is now live

Recording `ts-golden-regen`'s plants brought it into the harm suite, and `scripts/audit_corpus`
immediately flagged a pair it shares vocabulary with:

| task | fact terms | `bare` |
|---|---|---:|
| `ts-golden-regen` | "never hand-edit", "regenerated only via the script" | 0.50 |
| `ts-ignore-gen` | "maintained only via the script", "sorted and deduped", "hand edits get lost" | 1.00 |

That is **one convention**, *do not hand-edit this generated file, run the script*, applied to two
artefacts: test goldens and an ignore file. The overlap score is 0.33 on `hand`, `only`, `script`,
`via`.

The overlap is **pre-existing**; both `task.json` files are unchanged on master. What is new is
that both tasks are now in the same grid, which is when it starts to matter: the per-task cluster
bootstrap treats them as two independent units, and a product that misunderstands this one
convention fails both. `official-001` already showed a memory arm failing `ts-ignore-gen` in three
of twelve cells, so this is not hypothetical.

Three options, none taken yet because each is a measurement decision:

1. **Cluster them as one unit** in the bootstrap. Most honest, costs nothing, and keeps both tasks.
2. **Retire `ts-ignore-gen`.** It sits at `bare` = 1.00 and can only measure harm, while
   `ts-golden-regen` at 0.50 measures both, so if one goes it should be the former.
3. **Re-axe one convention** so the two are genuinely independent. Most work, best instrument.

⚠️ The audit prints this as a warning and exits 0, so CI does not stop it. A warning nobody acts
on is a warning that will still be there at the next run; this section exists so the decision is
recorded rather than rediscovered.

**Decision taken, same day: option 1.** `harness.stats.CONVENTION_CLUSTERS` maps both tasks to one
resampling unit, `cluster_bootstrap` collapses on it, and `summarize_by_task` publishes
`n_clusters` beside `n_tasks` so a reader can see the collapse rather than infer it. Option 3
would give a better instrument and was rejected on cost: re-axing either convention invalidates
plants and recorded sessions that already exist for both tasks.

The asymmetry is what makes this safe to do from a warning rather than from a measurement.
**Collapsing correlated units can only widen an interval, never narrow one.** Being wrong here
costs confidence; being wrong the other way costs correctness, and publishes an interval that is
too tight. Verified on a worked example: 0.450 wide becomes 0.600.

🔁 Acting on it also uncovered a defect the warning had nothing to do with. `summarize_by_task`
carried its **own copy** of the bootstrap while `cluster_bootstrap`'s docstring described itself
as "THE single implementation", a claim written after exactly that duplication had caused two
answers to "what is the CI". The copy computed every `cluster_ci` the harm suite publishes, so the
shared function and the published number came from different code, one function apart.
`tests/test_convention_clusters.py` now asserts the docstring's claim is true.

## 9. 🔁 Correction to section 4, appended 2026-08-30: "the only lever" is embedder-specific

Section 4 says corpus scale is **"the only lever that raises difficulty for the memory arms
without moving `bare`"**. A parallel measurement retires the general form of that claim.

A retrieval-only probe (fixed BM25 over 160-word windows, plus a hosted voyage-4 backend, no model
and no spend) was run against the frozen feed and against a 25x corpus assembled beside it:

| corpus | BM25 hit@1 | voyage hit@1 | voyage hit@10 |
|---|---:|---:|---:|
| real feed, 195 documents | 0.485 | 0.394 | **1.000** |
| 25x, no hard negatives | 0.485 | 0.394 | 0.939 |
| 25x, default mix | 0.182 | 0.333 | 0.879 |

Adding 4,680 ordinary sessions moved BM25's competitor count from 2.42 to 2.45, which is nothing,
and moved Voyage's from 1.79 to 7.36. Prompt-vocabulary hard negatives supply 72.5% of BM25's
competitors and 33.0% of Voyage's.

**So scale is a lever against an embedder and close to no lever against a term ranker**, and which
lever bites depends on what the product retrieves with. Section 4's recommendation to grow the
corpus stands; its claim to be the *only* such lever does not, and hard negatives built from a
task prompt's own vocabulary are the lever a term ranker responds to.

### It also sharpens the reranker question rather than settling it

`voyage hit@10 = 1.000` on the real feed **reconciles** preregistration 014's `hit@1 = 20/20`
rather than contradicting it: a reranker over the top k starts from a perfect candidate set there,
so there is genuinely nothing for it to win. On the 25x corpus the correct session is ranked first
only 33% of the time and falls outside the top ten 12% of the time, so the candidate set itself
degrades.

⚠️ That probe measures the CORPUS, not any product's own retrieval pipeline, so it motivates
re-taking 014's decision to disable the reranker without settling it. It arrives at the same place
as section 7 of this review by a different route: the metric that justified the decision cannot
see the failure mode that dominated the run.

⚠️ **The haystack is a THIRD feed.** Nothing measured on it may be differenced against the
125-entry or 195-entry feeds, which is every run this repository has published, `official-001`
included.
