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

## Results, measured 2026-08-30

Command, four seconds, no model and no money:

```bash
python -m scripts.generate_haystack --scale 25 --seed 1 && python -m scripts.retrieval_probe --corpus corpus --corpus corpus/haystack/scale-25/seed-1
```

Artifacts: `results/retrieval/015-bm25.json`, `results/retrieval/015-bm25-ablation.json`.
Generator digest `51368745d9ec`, 33 queries, zero misses at every scale, zero sessions discarded
for containment.

| corpus | documents | windows | hit@1 | hit@5 | hit@10 | mrr@10 | median rank | mean above gold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| real feed | 195 | 1,209 | 0.485 | 0.758 | 0.970 | 0.598 | 2 | 2.42 |
| 25x, default mix | 4,875 | 20,685 | **0.182** | 0.424 | 0.576 | 0.280 | 8 | 8.48 |

### The predictions, scored

| # | predicted | measured | verdict |
|---|---|---|---|
| 1 | baseline `hit@1` 0.79 | **0.485** | falsified, and in the informative direction |
| 2 | 25x `hit@1` 0.55 | **0.182** | falsified: the drop was 30 points, not 24 |
| 3 | mean competitors 1.5 to 15 | 2.42 to 8.48 | both ends missed, direction right |
| 4 | median rank stays 1 | 2 at baseline, 8 at 25x | falsified at both ends |
| 5 | near-miss ≥ 30% of competitor mass | **72.5%** at 9.6% of the corpus | confirmed, 7.5x concentration |
| 6 | `dense` `hit@1` 0.60 at 25x | **not run** | see below |
| 7 | `all_shards@10` below `hit@10` | 0.667 against 0.970; 0.333 against 0.576 | confirmed |

Five of seven predictions were wrong. The two that were closest to right, 5 and 7, are the two
that were about the mechanism rather than about the level.

### What the numbers say that no prediction anticipated

An ablation was run after seeing the above and is therefore **exploratory, not preregistered**.
It splits the 25x corpus into its two components:

| corpus | documents | near-miss | hit@1 | median rank | mean above gold |
|---|---:|---:|---:|---:|---:|
| real feed | 195 | 0 | 0.485 | 2 | 2.42 |
| 25x, **near-miss share 0.0** | 4,875 | 0 (0.0%) | **0.485** | 2 | 2.45 |
| 780 documents, near-miss share 0.8 | 780 | 468 (60.0%) | **0.242** | 7 | 7.21 |
| 25x, default mix | 4,875 | 468 (9.6%) | 0.182 | 8 | 8.48 |

**Adding 4,680 ordinary sessions changed retrieval by nothing at all.** `hit@1` is 0.485 before
and 0.485 after; the mean competitor count moves from 2.42 to 2.45; the median rank stays 2. A
25x corpus built out of background and topical work is exactly as easy to retrieve from as the
195-document corpus it grew out of.

**468 hard negatives in a 780-document corpus did more damage than 4,212 ordinary sessions in a
4,875-document one**, on every column.

So the claim in `docs/reviews/2026-08-30-instrument-review.md` section 4, that "corpus scale is
the only lever that raises difficulty for the memory arms without moving `bare`", is **wrong on
this instrument**. Scale is not a lever at all. The lever is the density of documents that
compete with the query, and scale only matters because a bigger corpus has room for more of
them: the same 468 near-misses cost 4 more points of `hit@1` when embedded in 4,875 documents
than in 780.

That correction is the most useful thing this run produced, and it was cheap enough to find only
because the probe needs no model. It also says what the next haystack should be: near-miss share
is the parameter to sweep, not scale.

### Prediction 6 was not run, and why that matters

The dense backend was **not** run. The user's standing instruction is that embedding runs on
VPS2 and not on this workstation, for every project, and `fastembed` is recorded as absent on
VPS2. So the semantic axis is unmeasured, and the honest statement of what is known is narrower
than this record was written to claim:

⚠️ **Everything above shows that near-misses generated from prompt vocabulary defeat a TERM
ranker. Nothing here shows they defeat an EMBEDDING ranker**, and every product this benchmark
compares retrieves with embeddings. If a dense backend scores near 1.00 on the 25x corpus, the
haystack is hard only for BM25 and the near-miss construction needs redesigning around semantic
rather than lexical adjacency. That measurement is the blocking next step, not an extra.

### Two things that are safe to conclude, and one that is not

Safe: the real 195-document corpus poses a **weaker** ranking problem than the review estimated,
since a fixed BM25 already puts the right session first only 48.5% of the time; and the corpus
can be made materially harder for a lexical retriever, cheaply and reproducibly.

Not safe: any comparison between `hit@1 = 0.485` here and the `hit@1 = 20/20` in
preregistration 014. Those are different instruments over different query sets. This record
retires neither that number nor the reranker decision that cited it; it says only that the
corpus behind it had few competitors, which is what the review already argued.
