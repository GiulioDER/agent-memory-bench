# Protocol change record, 2026-08-29

Three CONFIRMED findings from the 2026-08-28 CCA audit were held back from that audit's fix PR
(#8) because each one moves a number a frozen preregistration rests on. They are landed here,
deliberately and together, with the break stated rather than absorbed.

**Nothing above any results marker has been edited.** This document is the change record; the
affected preregistrations carry a pointer to it appended below their markers.

## Summary of the break

| Change | What it moves | Runs affected |
|---|---|---|
| `oracles/ts-retry-cap/driver.py` growth check pooled | `ts-retry-cap` success rates, all arms | any future run |
| `harness/tasks.py run_checker` guards the checker | paired-cell **admission** rate | any future run |
| `harness/costs.py` prices input classes separately | `estimated_usd` only, no success rate | any future run, plus the appendix below |

**Consequence for the GPT-5.3 rerun.** The resume plan calls for rerunning `pilot-003-gpt53`
"with the exact frozen protocol". After these changes that is no longer available: a rerun uses a
grader that rejects fewer correct solutions and an admission rule that discards fewer cells. A
GPT rerun is therefore comparable to a **DeepSeek rerun on this same code**, not to the recorded
`pilot-003-deepseek`. Either rerun both arms of the model comparison, or state in the report that
the model contrast is measured on a revised instrument.

---

## 1. `ts-retry-cap` rejected correct solutions about 40% of the time

The grader required `max(delays) >= 20.0` on ONE run of the always-down scenario. With 8 attempts
the sleep caps are 1, 2, 4, 8, 16, 30, 30, so only the last two draws can exceed 20. An
implementation using AWS-canonical **full jitter**, `random.uniform(0, min(30, 2**attempt))`,
cleared the check only when one of two U(0,30) draws landed above 20: expected failure rate
(2/3)² ≈ 44%. Nothing seeded the RNG, so the same submission passed or failed between runs.

The committed `informed` reference adds U(0,1) to a capped exponential and maxes near 31 every
time, which is why `tests/test_references.py` never saw it: the reference is not the population
the grader has to judge.

Measured over 40 runs per implementation style, before and after:

| style | before | after |
|---|---|---|
| `informed` (committed reference) | 40/40 pass | 40/40 pass |
| full jitter (AWS canonical) | **25/40 pass** | 40/40 pass |
| equal jitter | **35/40 pass** | 40/40 pass |
| naive constant 1s | 0/40 pass | 0/40 pass |
| small linear ramp (0.1 … 0.7) | 0/40 pass | 0/40 pass |

Equal jitter was affected too, at about 12%, which was not predicted before measuring.

The fix pools the growth-magnitude check over 16 runs of the same scenario (no real time passes,
so the cost is a few thousand function calls). Discriminating power is unchanged: what the check
separates is capped exponential growth from a small constant or linear sleep, and both of those
still fail 40/40. Residual spurious-failure probability for full jitter is (2/3)^32, about 5e-6.

**Effect on recorded runs.** `ts-retry-cap` failures in `pilot-002` through `pilot-004` include an
unknown number of spurious ones. The error is symmetric across arms (nothing about it depends on
which arm produced the solution), so it inflated variance rather than biasing the recall-versus-
`claude_md` contrast in either direction. The recorded numbers are left exactly as they are.

## 2. A checker crash discarded the whole paired cell

`run_checker` let an exception propagate. `harness.runner` turned it into an error record and
`harness.gate` then discarded the cell for "the session did not complete", taking **every other
arm's paid session in that cell with it**.

The trigger is agent-controlled, which is what makes it a scoring hole rather than an
infrastructure one: several checkers read an agent-written file with a strict UTF-8 decode, so an
artifact written in cp1252 on Windows raised. A task whose deliverable the grader cannot read is a
task that was not solved; scoring it as a discard let a bad deliverable delete the evidence for
its own cell, and pushed the run toward the frozen 95% admission floor.

A checker that raises now grades as a **failure**, with the exception type and message as its
verdict. A genuine harness fault (missing checker file, syntax error in one) still raises, because
`_load_callable` runs outside the guard: that is a defect in the instrument, not an outcome.

**Effect on admission.** Strictly upward: cells that would have been discarded are now graded.
Any run measured after this change has an admission rate that is not comparable to the frozen
runs' on a like-for-like basis.

## 3. Cost estimates charged cache reads at the fresh-input rate

`ModelPricing.usd` applied one rate to all input, while `SessionRecord.input_tokens` is the sum of
three differently-priced classes: fresh, cache read, and cache creation. `harness/claude_exec.py`
had recorded the split per session from the beginning, and said in a comment that the classes "are
not priced alike"; only the pricing ignored it.

The classes are now priced separately, and the artifact publishes the rates that produced its
dollars alongside the split. Absent a published cache rate the behaviour is unchanged and
`priced_cache_separately` reports `false`, so a reader can tell which of the two they are looking
at instead of assuming.

### Appendix: recomputation of the published runs

Recorded numbers are NOT edited. This is a recomputation beside them.

Cache-read share of each arm's input, measured from `records.final.jsonl`:

| run | bare | claude_md | placebo | recall |
|---|---:|---:|---:|---:|
| `pilot-003-deepseek` | 44.4% | 48.6% | — | **68.2%** |
| `pilot-004-placebo` | 58.2% | 56.8% | 55.4% | **68.2%** |

The recall arm's input is roughly two-thirds cache reads in both runs, well above every baseline,
so one rate for all three classes overstates spend **unevenly between the arms being compared**.

`estimated_usd` by cache-read discount ratio (1.00 = the published behaviour). The exact provider
rate is deliberately not asserted here: it must come from a dated price capture, and the
structural result does not depend on it, since every ratio below 1.00 shrinks the premium.

**`pilot-003-deepseek`**

| arm | ×1.00 (published) | ×0.50 | ×0.25 | ×0.10 |
|---|---:|---:|---:|---:|
| bare | 0.0824 | 0.0673 | 0.0597 | 0.0552 |
| claude_md | 0.0863 | 0.0690 | 0.0603 | 0.0551 |
| recall | 0.3277 | 0.2229 | 0.1705 | 0.1391 |
| **total** | **0.4964** | 0.3592 | 0.2905 | 0.2494 |
| recall ÷ claude_md | 3.80× | 3.23× | 2.83× | 2.52× |

The ×1.00 column reproduces the committed `costs.json` exactly, which is what validates the
recomputation.

**`pilot-004-placebo`**

Priced on **its own basis**, the argparse defaults 0.05866 / 0.11732, for the reason given in the
next section. Its ×1.00 column likewise reproduces its committed `costs.json` exactly.

| arm | ×1.00 (published) | ×0.50 | ×0.25 | ×0.10 |
|---|---:|---:|---:|---:|
| bare | 0.0933 | 0.0706 | 0.0592 | 0.0523 |
| claude_md | 0.0842 | 0.0643 | 0.0543 | 0.0484 |
| placebo | 0.0864 | 0.0666 | 0.0566 | 0.0507 |
| recall | 0.3196 | 0.2182 | 0.1675 | 0.1371 |
| **total** | **0.5836** | 0.4196 | 0.3376 | 0.2885 |
| recall ÷ claude_md | 3.80× | 3.39× | 3.08× | 2.83× |

### A second finding, surfaced by doing the recomputation

**The two published runs were priced at DIFFERENT rates, and neither artifact says so.**

Token counts reproduce exactly (`pilot-004` sums to 9,386,264 metered tokens, the recorded
figure). The dollars did not, by a uniform factor of 1.0219 across all four arms — which is
exactly `0.05866 / 0.0574`.

- `pilot-003-deepseek` was priced at the **frozen preregistration 002 rates**, 0.0574 / 0.1148.
- `pilot-004-placebo` was priced at **`scripts/pilot.py`'s argparse defaults**, 0.05866 / 0.11732.

Recomputing `pilot-004` at the defaults reproduces its published per-arm figures to four decimal
places on all four arms and the total. The run was launched without explicit `--price-in` /
`--price-out`, and nothing in `costs.json` recorded which basis was used, because the artifact
stored `pricing_as_of` and `pricing_model` but never the prices.

**So `pilot-003` and `pilot-004` dollar figures are not directly comparable**, independently of
the cache-read question. `to_dict` now publishes the rates, so this cannot recur silently. Making
`--price-in` / `--price-out` required rather than defaulted is the obvious follow-up and is NOT
done here, because it changes a CLI contract that the frozen runs used.
