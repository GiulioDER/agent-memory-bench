# 015-corpus-scale: does a 25x corpus make retrieval hard, or only make it big?

Status: DRAFT until committed; a committed record is frozen above the results marker.

Written 2026-08-30, before `scripts/retrieval_probe.py` had been run against any corpus.

## Question

Does growing the experience corpus 25x, with the tier mix in `scripts/generate_haystack.py`,
measurably degrade retrieval of the correct session, and which tier does the degradation come
from?

## Why this is asked at all

`docs/reviews/2026-08-30-instrument-review.md` section 4: the bench corpora are 951 to 1,129
chunks, an order of magnitude smaller than one real memory store (9,801). `hit@1 = 20/20` was
cited in preregistration 014 to justify disabling a reranker. A retrieval metric pinned at its
ceiling and a solved retrieval problem are indistinguishable, so that number is evidence about
the corpus, not about the retriever.

Nothing in this repository has ever measured rank. This record covers the first measurement, and
the instrument is deliberately **not** a product: a fixed stdlib BM25 over the same windows for
every corpus, so a difficulty number is comparable across months and across vendors.

## Instrument

| | |
|---|---|
| query | the task prompt, verbatim, which is what a memory arm has at turn 0 |
| unit | 160-word windows, stride 120; a session scores as its best window |
| gold | the sessions under `sessions/<task_id>/`; a hit at k is any of them in the top k |
| backend | `bm25`, Okapi, k1 = 1.2, b = 0.75, untuned |
| second backend | `dense`, fastembed `BAAI/bge-small-en-v1.5`, reported separately, never pooled |
| corpora | `corpus` (195 documents) and `corpus/haystack/scale-25/seed-1` (4,875 documents) |
| mix at 25x | background 0.70, topical 0.20, near-miss 0.10 |

No model is called and no money is spent, so this can be re-run at every corpus size and every
mix. That is the point: the difficulty curve, not one number.

## Endpoints, in reporting order

1. Primary: `hit@1` on `bm25`, real corpus against 25x corpus.
2. `mean_competitors_above_gold`, the same contrast. Rank degrades before `hit@1` does.
3. `competitor_tiers`: the share of wrong-sessions-ranked-above-gold contributed by each tier,
   against that tier's share of the corpus. A tier that competes at its population share adds
   volume; a tier that competes above it adds difficulty.
4. `median_rank` at both scales.
5. `hit@1` on `dense` at both scales, reported beside `bm25` and never averaged with it.
6. `all_shards@10` for the three `xs-*` tasks, where finding one shard is not finding the fact.

## Predictions

Predicting low, per the house prior. Written before the first run of the probe.

1. **Baseline `hit@1` on the real 195-document corpus is 0.79 (26 of 33 queries), not 1.00.**
   The 156 real distractors were recorded on the task fixtures themselves, so they already share
   filenames and domain vocabulary with the prompts. If the baseline comes back at 1.00 the
   corpus is even less discriminating than the review argued.
2. **`hit@1` at 25x falls to 0.55**, a drop of about 24 points.
3. **`mean_competitors_above_gold` rises from about 1.5 to about 15.**
4. **`median_rank` stays 1 at both scales.** The median task stays easy; the loss is in the tail.
   If this holds it means corpus SIZE alone is a weak lever and near-miss DENSITY is the strong
   one, which decides what the next haystack looks like.
5. **The near-miss tier contributes at least 30% of competitor mass while being 10% of the
   corpus**, a concentration of 3x or more. This is the prediction that says the tier design
   works rather than merely runs.
6. **`dense` `hit@1` at 25x is 0.60**, five points above `bm25`, because an embedding ranker is
   less swayed by shared surface vocabulary than a term ranker is.
7. **`all_shards@10` is below `hit@10`** at both scales, because two sessions both have to
   survive the same ranking.

## What would falsify this

- `hit@1` at 25x at or above 0.90 with `mean_competitors_above_gold` below 3. The haystack would
  then have added 24 MB of volume and no difficulty, and the tier construction would be wrong
  rather than merely weak.
- The near-miss tier contributing at or below its 10% population share. The hard negatives would
  not be hard, and generating them from prompt vocabulary would be a failed idea.
- A baseline `hit@1` of 1.00 **with** a mean competitor count below 0.5, which would say the real
  corpus never posed a ranking problem at all and that every retrieval claim made from it, in
  either direction, is uninformative.

## Exclusion rules

- Tasks with no session under `sessions/<task_id>/` are skipped, not scored as misses. A task
  whose fact was never recorded is a corpus defect and is reported by
  `scripts/audit_corpus.py`, not by this probe.
- Both corpora are probed with the identical binary in the same invocation. A difficulty number
  is never compared against one produced by a different window size or different BM25 constants.

## What this deliberately does NOT claim

This measures the corpus, not any product. A vendor's own retrieval can beat or lose to BM25 for
reasons that have nothing to do with corpus difficulty. No arm-level or product-level claim may
cite this record. The next question, whether a 25x corpus changes task success, is a live run
and needs its own preregistration and its own budget.

⚠️ **A number measured on the 25x haystack is not comparable with `pilot-003`, `pilot-004` or
`abstention-001`.** Those ran against the 125-entry and 195-entry feeds. The haystack is a third
feed. See `docs/audit/2026-08-29-corpus-feed-change-record.md` for the same hazard the last time
the feed moved.

<!-- results are appended below this line; everything above is frozen -->
