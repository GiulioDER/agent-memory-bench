# Retrieval difficulty: how hard this corpus is, and how to make it harder

Dated 2026-08-30. Every number below is re-derived by the command beside it.

`docs/reviews/2026-08-30-instrument-review.md` section 4 said the corpus was too small to
challenge retrieval and that `hit@1 = 20/20` was evidence about the corpus rather than about any
retriever. That was right. Its proposed remedy, "corpus scale is the only lever that raises
difficulty", was **wrong**, and this document is mostly about why.

## The two tools

```bash
python -m scripts.generate_haystack --scale 25 --seed 1
python -m scripts.retrieval_probe --corpus corpus --corpus corpus/haystack/scale-25/seed-1
```

The first assembles a corpus root of 4,875 documents (20 MB, 20 seconds) beside the frozen
195-document feed. The second measures how hard it is to retrieve from, with a fixed stdlib
BM25, no model call and no money, in about 20 seconds. Neither touches `corpus/manifest.json`.

## What was measured

33 queries, one per task with recorded sessions, each query being the task prompt verbatim.

| corpus | documents | near-miss | hit@1 | median rank | mean competitors above gold |
|---|---:|---:|---:|---:|---:|
| the real feed | 195 | 0 | 0.485 | 2 | 2.42 |
| 25x, **no hard negatives** | 4,875 | 0 | **0.485** | 2 | 2.45 |
| 780 documents, 60% hard negatives | 780 | 468 | 0.242 | 7 | 7.21 |
| 25x, default mix | 4,875 | 468 (9.6%) | **0.182** | 8 | 8.48 |

Full record, including the seven predictions and the five that were wrong:
`preregistration/015-corpus-scale-retrieval-difficulty.md`.

## The finding

**Volume is not difficulty.** Adding 4,680 ordinary sessions to the corpus moved `hit@1` from
0.485 to 0.485. The mean number of wrong sessions ranked above the right one went from 2.42 to
2.45. A retriever that could answer the 195-document corpus can answer the 25x one just as well,
because nothing in those 4,680 documents competes with any query.

**Density is difficulty.** 468 hard negatives, generated from the task prompts' own vocabulary,
took `hit@1` to 0.182 and the median rank from 2 to 8. They are 9.6% of the 25x corpus and
supply **72.5%** of the sessions ranked above the correct one: a concentration of 7.5x. In a
780-document corpus the same 468 documents do most of the same damage, so the corpus does not
need to be large to be hard.

Scale still earns its place, for three reasons that are not ranking difficulty:

1. it is where hard negatives have room to live, and the same 468 cost four more points of
   `hit@1` at 4,875 documents than at 780;
2. ingest cost, index build time and query latency are real product properties that a
   195-document corpus cannot exercise at all;
3. a store an order of magnitude smaller than any real one is not a credible test of a product
   sold for real ones.

But a benchmark that grew the corpus and stopped there would have spent 20 MB and changed
nothing it was trying to change.

## What is NOT known, and it is the important part

⚠️ **The dense backend has not been run.** Everything above is a **term** ranker. Every product
this benchmark compares retrieves with embeddings, and a near-miss built out of shared surface
vocabulary is exactly the kind of hard negative an embedding model might not fall for.

So the honest statement is: the corpus can be made hard for BM25, cheaply and reproducibly, and
whether it is hard for a semantic retriever is **unmeasured**. Until that is run, no claim of
the form "this benchmark tests retrieval" is supported.

The probe already has the backend:

```bash
python -m scripts.retrieval_probe --backend dense --corpus corpus --corpus corpus/haystack/scale-25/seed-1
```

It was not run here because the standing instruction for every project on this machine is that
embedding runs on VPS2 and not on this workstation, and `fastembed` is recorded as absent on
VPS2. That is an environment decision to make, not a measurement to skip quietly.

If dense `hit@1` on the 25x corpus comes back near 1.00, the near-miss construction needs
rebuilding around semantic adjacency: same *meaning* neighbourhood, different scope, rather than
same words.

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
