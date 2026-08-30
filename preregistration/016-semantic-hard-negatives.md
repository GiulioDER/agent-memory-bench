# 016-semantic-negatives: does a hard negative built from meaning beat one built from words?

Status: DRAFT until committed; a committed record is frozen above the results marker.

Written 2026-08-30, after `015` and before the `semantic` tier had been probed against anything.

## Question

Does a near-miss generated from a task's semantic **neighbourhood**, sharing no distinctive token
with that task's prompt, compete with the gold session against an embedding retriever better than
a near-miss generated from the prompt's own **vocabulary** does?

## Why this is asked

`015` measured that the two rankers fail on different documents. Prompt-vocabulary near-misses
took `bm25` from 0.485 to 0.182 and `voyage-4` only from 0.394 to 0.333, supplying 72.5% of BM25's
competitors against 33.0% of Voyage's. The tier that hurt `voyage-4` most was `topical`, which
shares no query terms at all: 123 competitors from 936 documents while costing BM25 literally
zero.

Every product this benchmark compares retrieves with embeddings, so the lexical negative is the
weaker lever for the thing being measured. This tests the obvious inference from `015`, which is
that the strong lever is meaning rather than words.

## The construction under test

`scripts/haystack_neighbourhoods.py`: one authored neighbourhood per task, each with a subject, a
term set and a settled decision. Three rules, the first two mechanically enforced:

1. **No term appears in its own task's prompt.** Verified: zero distinctive overlaps across all
   33 tasks, function words excluded.
2. **Nothing states any task's `fact_terms`.** Verified: zero leaks, and every emitted file is
   re-checked by the generator.
3. **The decision sits on an axis the task does not ask about** (retention rather than mutation,
   permissions rather than durability, locale rather than timezone). This is judgement and is
   NOT mechanically enforced; it is what keeps a hard negative from being a `contradictory`
   plant.

Authored rather than mined, deliberately. Selecting the documents `voyage-4` ranks closest and
then scoring difficulty with `voyage-4` measures the selection, and the corpus would stop being
hard the moment anyone changed embedder.

## Grid

| | |
|---|---|
| instrument | `scripts/retrieval_probe.py`, unchanged from `015`: 160-word windows, stride 120, BM25 k1 = 1.2 b = 0.75, `voyage-4` for the semantic axis |
| corpus A | 25x, mix background 0.60 / topical 0.15 / near_miss 0.10 / **semantic 0.15**, 4,875 documents |
| corpus B | 780 documents, **semantic 0.80**, near_miss 0.00, the isolation arm directly comparable to `015`'s near-miss-only 780-document corpus |
| baselines | `015`'s numbers, not re-run: 25x default mix, and the 780-document near-miss-only corpus |
| queries | the 33 task prompts, verbatim, as in `015` |

## Endpoints, in reporting order

1. Primary: `voyage` hit@1 on corpus A, against `015`'s 0.333.
2. The `semantic` tier's share of `voyage` competitor mass, against its 15% population share.
   A tier that competes at its share adds volume; above it, difficulty.
3. Corpus B against `015`'s near-miss-only 780-document corpus, `voyage` hit@1 and mean
   competitors. This is the like-for-like test of meaning against words at equal document count.
4. `bm25` on both corpora, to confirm the semantic tier is not secretly lexical.
5. `voyage` hit@10 on corpus A, which is the number that says whether this is still only a
   ranking problem.

## Predictions

Predicting low, per the house prior. Written before the probe was pointed at either corpus.

1. **`voyage` hit@1 on corpus A is 0.24**, down from 0.333, a fall of about 9 points.
2. **The `semantic` tier supplies at least 30% of `voyage` competitor mass at 15% of the
   corpus**, a concentration of 2x or better, and beats `topical`'s 1.8x from `015`.
3. **On corpus B, `voyage` hit@1 is 0.27 against the lexical arm's 0.333**, so meaning beats
   words by about 6 points at equal document count. This is the endpoint the whole record exists
   for and it is the one I am least confident about.
4. **`bm25` hit@1 on corpus A stays within 3 points of `015`'s 0.182**, and the `semantic` tier
   supplies **under 10%** of BM25's competitor mass, below its 15% population share. If it
   supplies more, the neighbourhoods are lexically adjacent after all and rule 1 was too weak a
   test.
5. **`voyage` hit@10 on corpus A is 0.79**, down from 0.879. Still not a retrieval failure
   problem.

## What would falsify this

- The `semantic` tier supplying at or below its 15% population share of Voyage competitors. The
  authored-neighbourhood idea would then have failed on its own terms, and hard-negative mining,
  with its circularity accepted and disclosed, becomes the fallback.
- Corpus B scoring at or above the lexical 780-document corpus on `voyage` hit@1. Meaning would
  then be no better than words for the retriever that matters, and the cheaper lexical
  construction should simply be used at higher density.
- `bm25` moving more than 3 points on corpus A while `voyage` moves less than 3. That would say
  the tier is lexical after all and the enforcement in rule 1 does not do what it claims.

## Exclusion rules

- `015`'s numbers are quoted, not re-measured. Both records use the same probe, same window
  size, same constants and the same 33 prompts, which is what makes them comparable; any change
  to the probe invalidates the comparison and requires re-running both.
- The `background` and `topical` shares differ between `015`'s mix and corpus A (0.70/0.20
  against 0.60/0.15), because the semantic tier had to come from somewhere. Corpus A is
  therefore **not** a clean single-variable contrast with `015`'s 25x corpus, and endpoint 3
  exists precisely because corpus B is one.

## What this deliberately does NOT claim

Nothing about any product. Rule 3 above is unenforced judgement, so if a semantic near-miss ever
turns out to answer a task's question in the wrong direction it is a corpus defect that would
corrupt task-success runs, and the response is to fix the neighbourhood, not to reinterpret the
result.

<!-- results are appended below this line; everything above is frozen -->
