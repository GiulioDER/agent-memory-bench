# Retrieval difficulty: how hard this corpus is, and how to make it harder

Dated 2026-08-30. Every number below is re-derived by the command beside it.

`docs/reviews/2026-08-30-instrument-review.md` section 4 said the corpus was too small to
challenge retrieval and that `hit@1 = 20/20` was evidence about the corpus rather than about any
retriever. That was right.

Its proposed remedy, "corpus scale is the **only** lever that raises difficulty", is half right,
and which half depends entirely on which retriever you point at it. Scale is a strong lever
against an embedding ranker and no lever at all against a term ranker; hard negatives are a
strong lever against both. A first draft of this document said the remedy was simply wrong,
which was a conclusion drawn from BM25 before the semantic side had been measured, and is
corrected here rather than deleted because the error is the instructive part: **one retriever is
not enough to characterise a corpus.**

## The two tools

```bash
python -m scripts.generate_haystack --scale 25 --seed 1
python -m scripts.retrieval_probe --corpus corpus --corpus corpus/haystack/scale-25/seed-1
```

The first assembles a corpus root of 4,875 documents (20 MB, 20 seconds) beside the frozen
195-document feed. The second measures how hard it is to retrieve from, with a fixed stdlib
BM25, no model call and no money, in about 20 seconds. Neither touches `corpus/manifest.json`.
`--backend voyage` adds the semantic axis and is the one that costs money; see the end of this
file for how it is run and why it runs on VPS2.

## What was measured

33 queries, one per task with recorded sessions, each query being the task prompt verbatim. Two
rankers: a fixed stdlib BM25, and `voyage-4` (the family the production memory corpus is built
with), the API call originating on VPS2 so no model runs on this workstation.

| corpus | documents | near-miss | `bm25` hit@1 | `voyage` hit@1 | `voyage` hit@10 | `bm25` above | `voyage` above |
|---|---:|---:|---:|---:|---:|---:|---:|
| the real feed | 195 | 0 | 0.485 | 0.394 | **1.000** | 2.42 | 1.79 |
| 25x, **no hard negatives** | 4,875 | 0 | **0.485** | **0.394** | 0.939 | 2.45 | **7.36** |
| 780 documents, 60% hard negatives | 780 | 468 | 0.242 | 0.333 | 0.879 | 7.21 | 5.36 |
| 25x, default mix | 4,875 | 468 (9.6%) | **0.182** | **0.333** | 0.879 | 8.48 | 10.67 |

Full record, including the seven predictions and the five that were wrong:
`preregistration/015-corpus-scale-retrieval-difficulty.md`.

## The finding

**The two rankers fail on different corpora, and each is blind to what breaks the other.** That
is the whole result, and measuring only one of them produces a confident wrong conclusion in
either direction.

| | costs `bm25` | costs `voyage` |
|---|---|---|
| near-miss tier, 9.6% of the corpus | **72.5%** of competitors | 33.0% of competitors |
| topical tier, 19.2% | **zero** | 123 competitors, the largest single source |
| background tier, 67.2% | **zero** | 55 competitors |
| volume alone, 195 to 4,875 documents | mean above 2.42 → 2.45 | mean above 1.79 → **7.36** |

**Against a term ranker, volume is not difficulty.** Adding 4,680 ordinary sessions moved
`hit@1` from 0.485 to 0.485 and the mean competitor count from 2.42 to 2.45. Nothing in those
4,680 documents shares enough vocabulary with any query to compete.

**Against a semantic ranker it is.** The same 4,680 documents quadrupled the competitor count,
1.79 to 7.36, while leaving `hit@1` unmoved at 0.394. The embedder finds topical neighbours that
share no query terms at all, which is exactly what BM25 cannot see.

**Hard negatives cost hit@1 on both, four times harder on the lexical one.** 468 near-misses
generated from the task prompts' own vocabulary took `bm25` from 0.485 to 0.182 and `voyage`
from 0.394 to 0.333. They are 9.6% of the corpus and supply 72.5% of BM25's competitors against
33.0% of Voyage's, so they are concentrated far above their population share for both, and much
further for the term ranker.

So the corpus needs both levers, and a benchmark that grew the corpus and stopped, or that added
hard negatives and stopped, would have tested half the failure surface each time.

## What is honestly still not hard

`voyage` hit@10 at 25x is **0.879**, and on the real 195-document corpus it is **1.000**. The
right session is still in the top ten for seven of eight tasks. **This corpus is now a genuine
ranking problem and is not yet a retrieval failure problem for a competent embedder.**

That reconciles the `hit@1 = 20/20` in preregistration 014 rather than refuting it. On a corpus
where hit@10 is 1.000, any reranker over the top k starts from a perfect candidate set, so a
product reporting 20/20 and this probe reporting 0.394 are consistent and are measuring
different stages.

⚠️ **It does retire the reasoning that justified disabling the reranker.** That rested on the
correct session already being ranked first. At 25x it is first 33% of the time and outside the
top ten 12% of the time, so reranking now has work to do and 12% of tasks are beyond its reach
entirely. Preregistration 014's configuration should not be carried onto a haystack corpus
without re-deciding this.

To go further, the near-miss construction has to move from lexical to semantic adjacency: same
meaning neighbourhood, different scope, rather than same words. The `topical` tier is the
evidence that this works, since it is the largest competitor source for `voyage` while costing
BM25 nothing.

```bash
ssh vps2 'cd ~/bench-probe && set -a && . ~/recall-repos/.env && set +a && ~/recall-repos/.venv/bin/python -m scripts.retrieval_probe --backend voyage --corpus corpus/haystack/scale-25/seed-1'
```

About 25 minutes for 46,000 windows across four corpora, roughly 9.1M tokens. ⚠️ There is no
incremental caching, so a failure on the last corpus discards the embeddings already paid for on
the earlier ones. Probe one corpus per invocation when the budget matters.

## What a synthetic session is, and what it is not

`corpus/README.md` rule 1 is that content is verbatim agent output. **That rule does not hold
for the haystack, and the haystack is therefore kept out of `corpus/distractors/`.** Generated
sessions live under `synthetic/` in an assembled root, with `haystack.json` recording the tier,
domain, theme, project and near-miss target of every one of them, and the sha256 of the
generator that produced them.

They are structurally real rather than verbatim: the tool results are real reads of a real
generated repository, so the bulk of a session's bytes is file content rather than narration
about file content. That is what makes them compete lexically. It does not make them recordings.

## Containment, and one thing it cost

Every emitted session is checked against every task's `fact_terms` with the same normalisation
`scripts/audit_corpus.py` uses, and a violator is discarded and regenerated. A near-miss is safe
by construction because audit assertion 3 already forbids a fact term from appearing in a task
prompt, and near-miss vocabulary is drawn from prompts.

The first run discarded 14 of 195 sessions and the discards were not random. **`glossary` is one
of `ts-nfc-count`'s fact terms**, so an entirely ordinary theme (write a GLOSSARY.md) was being
filtered out of the haystack while the log reported only a count. A generic English word held as
a fact term quietly removes a whole category of ordinary work from the distractor pool. The
generator now records discards by tier and by task for exactly this reason, and the theme was
renamed rather than the filter loosened.

```bash
python -c "import json;print(json.load(open('corpus/haystack/scale-25/seed-1/haystack.json'))['discarded_detail'])"
```

## Which tasks can carry a result

Related, and the other half of "does this benchmark measure anything":

```bash
python -m scripts.task_admission --retrieval results/retrieval/015-bm25-ablation.json
```

Pooling seven runs, 22 of 33 tasks can express an outcome today. Six are spend (every arm
already solves them), two sit on the floor (no arm has ever solved them, so they separate
nothing until one does), and three `xs-*` tasks have never been screened. The report names the
capacity rather than passing or failing a task, because benefit capacity and damage capacity are
independent and a suite that measures only one needs only one.

⚠️ A `bare` rate of 0.00 is **not** a dead task. Section 7 of the instrument review found the
largest memory effect in this repository on exactly those tasks. Calling them "too hard" is what
kept them out of `official-001`.
