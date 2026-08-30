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


---

## 🔁 Instrument change, 2026-08-30: the BM25 in this record no longer exists

Appended, not edited. Every number above stands as measured, and none of it is retracted. What
changed is the ranker underneath, so a number measured after this date is not comparable with one
above it.

**What happened.** Finding F-24 of the 2026-08-30 audit found a SECOND BM25 in the repository.
`scripts/retrieval_probe.py`, which produced every number in this record, had its own
implementation differing from `harness/retrieval.py` in four ways: `k1` (1.2 against 1.5), the
tokenizer (`[a-z0-9_]+` against `[a-z][a-z0-9_]*`), the stoplist (none against 48 words), and
whether query terms were deduplicated. There was a third partial copy in
`scripts/audit_findability.py`, which windowed at a different stride over a different text while
its comment said it matched. All three are now one implementation.

**One of the four was a defect, not a parameter.** The probe scored `set(tokenize(query))`.
Textbook BM25 sums over query terms, so a term appearing twice in a prompt contributes twice;
deduplicating silently discarded that weight.

**Attributable effect, corpus held FIXED and only the ranker varied.** Measured 2026-08-30 over
4,900 documents and the 34 real task prompts:

| ranker | hit@1 | hit@5 | hit@10 | mrr@10 |
|---|---:|---:|---:|---:|
| the one this record used | 0.1471 | 0.4412 | 0.5588 | 0.2533 |
| the same, query dedup removed | 0.2941 | 0.5882 | 0.7059 | 0.4118 |
| the unified ranker | 0.2941 | 0.5588 | 0.6765 | 0.3864 |

⚠️ **A second thing also moved, so do not attribute a rerun's whole delta to the ranker.** The
corpus feed went 195 to 196 documents on 2026-08-30 (`fa-dedup-key`), and a rebuilt 25x haystack
is 4,900 documents rather than 4,875. The table above is the clean attribution because it holds
the corpus fixed; a rerun changes both.

**Current state of the same probe**, measured 2026-08-30 on the unified ranker,
`results/retrieval/f24-unified-bm25.json`:

| corpus | documents | hit@1 | hit@5 | hit@10 | mrr@10 |
|---|---:|---:|---:|---:|---:|
| `corpus` | 196 | 0.500 | 0.882 | 0.941 | 0.623 |
| `corpus/haystack/scale-25/seed-1` | 4,900 | 0.294 | 0.559 | 0.676 | 0.386 |

**The parameters were NOT tuned to this corpus**, and the unified ranker is deliberately not the
hit@1-maximising configuration in the table above. `harness/retrieval.py` states the reason: a
reference ranker tuned against the corpus it scores would flatter or punish the arms measured
against it, and the number would mean less for looking better.

**One finding worth carrying forward.** Whether to score whole documents or 160-word windows is
NOT settled by this work, because the answer inverts with corpus size: over the 196-document feed
whole documents win (hit@1 0.6765 against 0.5000), and over the 4,900-document haystack windows
win (0.2941 against 0.2647). Neither is "the right unit", so every call site now says which it
uses.

Full account: `docs/audit/2026-08-30-audit-fix-record.md`. Re-measure:

```bash
python -m scripts.retrieval_probe --corpus corpus --corpus corpus/haystack/scale-25/seed-1 --backend bm25 --top 10
```
