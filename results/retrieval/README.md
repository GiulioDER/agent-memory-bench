# Retrieval probe results

Each file here is a `scripts/retrieval_probe.py --out` artifact: one JSON list, one entry per
corpus root probed, each with a `summary` and a `per_task` array.

This file exists because **an artifact cannot warn you about itself.** The numbers below were all
produced by a real run and none of them is wrong as a record of that run. What changes is the
instrument, and a reader comparing two files has no way to see that from inside them. That
already cost this project once: `pilot-003` and `pilot-004` were priced on different bases and
neither artifact said so, so their dollar figures were never comparable and looked it.

## ⛔ Do not difference these two against anything measured after 2026-08-30

| File | Corpus | `hit@1` | Measured |
|---|---|---:|---|
| `arm-fs-grep-base.json` | 195 documents | 0.6061 | before 2026-08-30 |
| `arm-fs-grep-25x.json` | 4,875 documents | 0.5455 | before 2026-08-30 |

Both were produced by the `fs_grep` arm's own ranked list, and the audit of 2026-08-30 found two
scoring defects in that ranker. Both are fixed, and fixing them **moved the arm's scores**:

- **Substring counting.** `sum(text.count(term) for term in terms)` scored one span once per
  query term that is a substring of it. Terms `{sort, sorting}` over the text `"sorting sorting"`
  scored **4** for two occurrences, so a document was rewarded for the query's morphology rather
  than for its own content.
- **Sentence-final terms were dropped entirely.** The token pattern keeps `.` so that dotted
  identifiers (`config.json`) survive as one term, which also meant a prompt ending
  `"...must stay relative."` produced the term `relative.`, and `text.count("relative.")` is 0
  against every document containing `relative`. Every sentence-final content word was silently
  absent from every query.

Detail, with the finding IDs and the red-state proof:
[`docs/audit/2026-08-30-audit-fix-record.md`](../../docs/audit/2026-08-30-audit-fix-record.md).

Re-measure either one on the current instrument, which is the only way to get a comparable pair:

```bash
python -m scripts.retrieval_probe --corpus corpus --arm fs_grep --gating raw --top 10
```

## ⚠️ Two more things that are true of every file in this directory

**`competitor_tiers` was computed over the wrong population until 2026-08-30.** Miss rows padded
the histogram with an arbitrary top-k prefix of a ranking that had failed, so a "what beats gold"
count included entries that beat nothing: 70 of 84 entries (83%) in one committed artifact came
from misses. Files written after that date carry `competitor_tiers_n_queries` beside it, and put
the miss diagnostic in a separate `miss_topk_tiers`. **In a file without those two keys, read
`competitor_tiers` as contaminated in proportion to `misses`.** Measured 2026-08-30 over every
file in this directory:

| File | queries | misses | `competitor_tiers` entries | from misses |
|---|---:|---:|---:|---:|
| `arm-fs-grep-25x.json` | 33 | 7 | 84 | 70 (83%) |
| `arm-fs-grep-base.json` | 33 | 3 | 54 | 30 (56%) |
| `015-*`, `016-*`, `018-*`, `adjacent-preflight*` | 33 | **0** | — | **none** |

So only the two `fs_grep` files are affected in fact. Everything else predates the fix and is
clean regardless, because a corpus with no misses has no miss rows to pad with. The "from misses"
column is `misses * top`, the size of the arbitrary prefix each miss row contributed:

```bash
python -c "import json,sys;[print(e['summary']['corpus'],e['summary']['misses'],sum(e['summary']['competitor_tiers'].values())) for e in json.load(open(sys.argv[1]))]" results/retrieval/arm-fs-grep-25x.json
```

**A file without a `corpus_sha256` names a directory, not a corpus.** `corpus/haystack/` is
gitignored (a 25x root is about 24 MB of transcripts), so every artifact here written before
2026-08-30 records a path that is not in the tree and cannot be pinned to any particular build of
it. Later files carry `corpus_sha256`, `generator_sha256`, `corpus_seed` and `corpus_scale`.
Rebuild a haystack root and verify it byte for byte with:

```bash
python -m scripts.generate_haystack --scale 25 --seed 1 --check
```

## ⚠️ The corpus feed itself has moved twice

`arm-fs-grep-base.json` reports `documents: 195`. The feed is **196** since `fa-dedup-key` landed
on 2026-08-30, and it was **125** before 2026-08-29. Records:
[`docs/audit/2026-08-29-corpus-feed-change-record.md`](../../docs/audit/2026-08-29-corpus-feed-change-record.md)
and [`docs/audit/2026-08-30-feed-change-fa-dedup-key.md`](../../docs/audit/2026-08-30-feed-change-fa-dedup-key.md).
The `documents` field in each summary is the honest way to tell which feed a file saw.
