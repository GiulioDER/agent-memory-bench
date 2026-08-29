# The recall arm moves to 0.10.0, because 0.9.8 cannot complete an ingest on this host

Status: DRAFT until committed; a committed record is frozen above the results marker.

Written 2026-08-29, after record 012 pinned 0.9.8 and after the first `abstention-002` launch died
on its first ingest. 012 said moving to the latest release "is a separate decision and belongs in a
record that predicts what moving it should do". This is that record.

## What happened

The run aborted on the `absent` ingest, before a single session was spent:

```
onnxruntime ... Failed to allocate memory for requested buffer of size 3221225472
```

That number is not approximate and it identifies the cause exactly. bge-small has 12 attention
heads and a 512-token limit, and the attention scores for a batch are
`batch x heads x seq x seq x 4 bytes`:

```
256 x 12 x 512 x 512 x 4 = 3,221,225,472
```

So fastembed was running its own default batch of **256**. Free physical memory on this host,
measured the same minute, was **3,748 MB**, with another session's test suite resident. The
container itself then exited 255, which is consistent with the same pressure.

## Why 0.9.8 cannot be made to work from outside

There is no supported way to bound that batch in 0.9.8:

| control | 0.9.8 | 0.10.0 |
|---|---|---|
| `RECALL_FASTEMBED_BATCH` | not read anywhere in the package | read by `_batch_size_from_env`, passed to the encoder |
| `RECALL_INDEX_BATCH_CHUNKS` | not read anywhere in the package | read in `index.py` |
| `recall index --batch-chunks` | flag does not exist | n/a |
| `DEFAULT_BATCH_CHUNKS` | 512 | 512 |

⚠️ The adapter has been setting `RECALL_INDEX_BATCH_CHUNKS=16` since it was written, with a comment
explaining that an unbounded batch is how an earlier index run died of a bad allocation. Against
0.9.8 **that environment variable is a no-op**, and the comment describes an intent the version in
use could not honour. That is worth recording on its own: a bound nobody checked was a bound
nobody had.

## The pin

```
recall-rag[fastembed]==0.10.0   from PyPI, in .venv-bench
RECALL_FASTEMBED_BATCH=16
RECALL_INDEX_BATCH_CHUNKS=32
```

At batch 16 the attention buffer is `16 x 12 x 512 x 512 x 4` = about **201 MB**, against 3 GiB.

0.10.0 also adds schema migration `0015_learned_sparse_chunk_index.sql`, applied to the run
database.

## The claim this changes nothing measurable is MEASURED, not asserted

Bounding a batch changes how many sequences are padded together, and padding is exactly where a
transformer implementation could differ. So it was checked rather than argued: twenty passages
including one long enough to force heavy padding, embedded at batch 4 and at batch 64.

```
max absolute difference between batch 4 and batch 64: 0.000e+00
identical: True
```

Bit-identical. Re-measure in about thirty seconds by embedding the same list at two batch sizes and
comparing.

## Predictions

1. **All four ingests complete.** No allocation failure, and the indexing process's peak resident
   set stays under **1.5 GB**. Mechanism metric beside it: the largest single allocation
   onnxruntime requests, which at batch 16 should be about 201 MB and must never approach 3 GiB.
2. **The version move is invisible in the endpoints.** I am moving for operability, not quality,
   and this run cannot separate the two. Falsified in the only sense that matters if anyone,
   including me, later reports an endpoint difference as evidence about 0.9.8 versus 0.10.0.
3. **Record 011's predictions stand unamended.** Nothing here touches an endpoint, a task, a plant,
   an arm, the instruction, the embedder or the trust mode.

## What this costs, stated plainly

This is **not a controlled version comparison** and nothing in `abstention-002` may be read as one.
Two things changed since `abstention-001`: the arm stopped being a mutable worktree (012) and the
version became 0.10.0 (this record). Neither was a free choice, and together they mean the recall
arm's subject is newly defined rather than newly compared. The first run with a defensible baseline
for that arm is this one.

The honest summary of 012 plus 013 is that the recall arm had **no version at all** until today.

<!-- results are appended below this line; everything above is frozen -->
