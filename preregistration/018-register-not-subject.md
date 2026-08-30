# 018-register: is semantic adjacency about register rather than about subject?

Status: DRAFT until committed; a committed record is frozen above the results marker.

Written 2026-08-30, after 016 failed and before generation 3 had been probed on any embedder.

## Question

016's authored neighbourhoods scored **0.57x** competitor yield against `voyage-4`, below their
population share. The diagnosis was that two necessary rules together (no word from the task's
prompt, and a decision on an orthogonal axis) left **business-process prose** against
**technical-convention prompts**, and that semantic adjacency for an embedder is dominated by
register rather than by which artefact a document concerns.

Does keeping the axis and changing the register fix it?

## The evidence the diagnosis rests on

Competitor yield per document on the 25x corpus against `voyage-4`, where above 1.0 means a tier
pulls its weight:

| tier | share of corpus | share of competitors | concentration |
|---|---:|---:|---:|
| `near_miss`, from prompt WORDS | 9.6% | 33.3% | 3.47x |
| `topical`, generic convention prose | 14.4% | 27.4% | **1.90x** |
| `semantic` v2, authored neighbourhoods | 14.4% | 8.3% | **0.57x** |

Generic `topical` beat bespoke `semantic` by 3.3x per document while knowing nothing about any
task. That is the whole reason to think register is the variable.

## What changed, and what did not

`scripts/haystack_neighbourhoods_v3.py`, one entry per task. **Kept**: no distinctive word from
the task's own prompt (enforced, 0 overlaps across 33 tasks) and no task's `fact_terms` anywhere
(enforced, 0 leaks). **Changed**: every entry is now a technical decision about a file, a format,
a field or a path. For `ts-crlf-export`, the order values appear in a written record and what an
absent value looks like, instead of who consumes the extract and on what schedule.

`--semantic-generation {2,3}` selects the vocabulary. Verified before running: the generation-2
corpus is **byte-identical** to the one 016 measured, manifest for manifest, and generation 3
differs in exactly the 702 `semantic` files. So this is a one-variable contrast and 016's Voyage
numbers are the baseline rather than something to re-measure.

## Already measured, and therefore not predicted

`bm25` on the 25x corpus: `hit@1` 0.182 under both generations. The `semantic` tier supplies 0
BM25 competitors under v2 and **1 of 287** under v3. Both generations are essentially invisible to
a term ranker, which is the design working: any movement on Voyage is semantic, not lexical
overlap that slipped in.

## Predictions

Predicting low, per the house prior. Written before generation 3 met any embedder.

1. **The v3 `semantic` tier reaches at least 1.4x concentration against `voyage-4`**, up from
   0.57x. This is the claim the record turns on, and it is the minimum that would make the tier
   worth its share of the corpus at all.
2. **It does not beat `near_miss`'s 3.47x.** Borrowed vocabulary is a stronger signal than
   borrowed meaning even for an embedder, and I expect that to survive the register fix.
3. **`voyage` hit@1 falls from 0.333 to 0.28.** A five-point drop, not more: 702 documents at
   14.4% of the corpus cannot do what 468 prompt-vocabulary documents did.
4. **`voyage` hit@10 falls from 0.879 to 0.84.** Still not a retrieval failure problem, and the
   honest reading stays that this corpus is a ranking problem.
5. **v3 lands between `topical` (1.90x) and `near_miss` (3.47x)**, because it has the right
   register AND task-specific targeting, where `topical` has only the first.

## What would falsify this

- v3 concentration at or below 1.0x. The register diagnosis would be wrong, two authored
  generations would have failed, and hard-negative mining becomes the path, with its circularity
  disclosed: mine with one embedder and score with another.
- v3 concentration at or below `topical`'s 1.90x. Task-specific targeting would then be adding
  nothing over generic same-register prose, and the cheaper generic tier should simply be run at
  a higher share instead of maintaining 33 authored entries.
- `bm25` moving more than 3 points between generations, which would mean v3 is lexically adjacent
  after all and the enforcement is not doing what it claims.

## Exclusion rules

- 016's Voyage numbers are quoted, not re-measured, and that is only legitimate because the
  generation-2 corpus is byte-identical. If it ever is not, both must be re-run.
- Same probe, same window size, same BM25 constants, same 33 prompts, same `voyage-4`.

## What this deliberately does NOT claim

Nothing about any product. This is a corpus construction question. A tier that competes better is
a harder benchmark, not a better memory layer.

<!-- results are appended below this line; everything above is frozen -->
