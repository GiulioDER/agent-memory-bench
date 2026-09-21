# Code4 hosted exact parity result

Date measured: 2026-09-20

Status: PASS for the isolated hosted parity gate. This was not an official AML Smoke or Full run.

## Bound inputs

1. Candidate variant: `C6_code4_exact_bm25`.
2. Candidate commit: `ad7bdcf7090504f90cb7baa0b8d33620cd084d5e`.
3. Candidate generation: `aml-code4-exact-bm25-v1`.
4. Corpus manifest SHA256: `58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`.
5. Verifier SHA256: `fc182fd8daf18f497af9418b39ca766ce20473f63a9b8354ab6ab933ee2578e6`.
6. Raw result SHA256: `5ffcc526696a4be060a043da097b2a63fff8e196e5b0766c3bc7f1297840fb65`.

The raw verifier recorded `candidate_commit` as null because it read `commit` instead of the
actual `/version` field `git_commit`. The verifier still refused any endpoint that did not report
the frozen C6 variant, exact dense mode, ordering profile, and renderer profile. The commit above
was independently read from `/version` immediately after the run. The raw JSON is preserved
unchanged.

## Result

1. All 34 hosted Top 100 rankings exactly matched the independent NumPy plus canonical BM25
   reference, including order.
2. Mean and minimum Top 100 overlap were both 100. Mean Jaccard was 1.0.
3. Hosted recall at 10 and recall at 100 were both 1.0.
4. Hosted and reference MRR were both 0.8611111111.
5. The earlier screen MRR was 0.8464052288. The only changed first relevant rank was
   `ts-schema-additive`, which moved from rank 2 to rank 1. The other 33 tasks matched their
   historical first relevant rank.
6. Add p50 was 330.15 ms and p95 was 555.00 ms with three workers.
7. Hosted Search p50 was 431.11 ms and p95 was 1073.16 ms.
8. The independent NumPy exact dense calculation p50 was 7.81 ms and p95 was 72.10 ms.

## Normalization boundary

Two of 1,220 windows contained decoded NUL characters originating from one distractor transcript.
PostgreSQL cannot store NUL in text, so the frozen hosted contract replaced those characters with
the visible NUL symbol before windowing and embedding. A local preflight proved all 1,220 resulting
hosted chunk identities matched the candidate implementation. This is the only measured renderer
difference from the historical raw screen. It did not reduce recall, MRR, or hosted reference
parity in this replay.

## Cleanup

The replay tenant was deleted in the verifier `finally` path. A direct post run database check
reported zero rows and zero tenants in the C6 table.
