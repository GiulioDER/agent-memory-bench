# Preregistration 094: RE-call anchor compiler v3 admission pilot

Status: frozen before any provider backed replay under this protocol.

Date frozen: 2026-09-19.

This is a local development experiment. It does not authorize an official AML Smoke or Full run.
The registered section ends at the results marker near the bottom. Measured results may be appended
below that marker without editing anything above it.

## Question

Do compact content bound anchors, bounded schema retry, exact text anchor recovery, extractive
fallback, unique record accounting, and a raw diverse rescue tail let the compiler pass the same
admission thresholds that compiler v2 failed?

## Frozen population and arms

Use the committed `corpus/manifest.json` containing 196 historical sessions and all 34 committed
retrieval tasks. Its SHA-256 is
`58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`.

Both arms receive byte identical sessions in manifest order. Search receives only each committed
task prompt, exact `user_id`, and Top K 100. Fact terms and retrieval labels are scorer only data.
Each task is captured once. No coding agent runs.

1. `V3_raw`: unchanged raw dense plus exact lexical storage and retrieval.
2. `V3_anchor_raw`: the identical raw path plus compiler v3 records and the registered raw rescue
   renderer.

The arms use separate run specific namespaces in the dedicated
`recall_aml_anchor_compiler_v3_chunks` table and `aml-anchor-compiler-v3` generation.

## Compiler v3 treatment

1. Source excerpts and offsets remain deterministic and byte exact.
2. Each model facing anchor identifier contains a deterministic sequence prefix plus 16 hexadecimal
   characters from the source bound SHA-256 digest. The full local source binding remains in the
   resolved span.
3. A malformed model schema is retried inside the same maximum of three provider attempts and the
   same 12 second timeout per attempt.
4. Valid cited anchors are retained when another cited identifier is invalid. An invalid identifier
   may be recovered only by locating a nonempty proposed field or entity as an exact substring of a
   source anchor. No semantic or fuzzy recovery is allowed.
5. Every factual field and entity remains an exact substring of a selected anchor. Empty grounded
   proposals receive one bounded verbatim field.
6. Deterministic fallback stores one bounded source quote as its factual field, limits entities to
   cited spans, and emits an event time only from a cited message.
7. Duplicate compiled payloads are removed by their final content derived chunk identifier before
   persistence. Add reports the number of unique compiled chunks it actually submits to storage.
8. Search preserves the original ranked first ten items. Ranks 11 through 100 first admit raw
   chunks from source sessions not represented in the head, in original retrieval order, then fill
   remaining slots in original order. This uses no labels, fact terms, answers, or task identity.

Accepted records carry `anchor-v3`. Fallback records carry `deterministic-fallback` and cannot
count as typed acceptance. Raw history remains stored for every eligible session.

## Independent audit and frozen gates

Run `scripts/recall_anchor_compiler_audit.py` against the original corpus bytes with accepted
profile `anchor-v3`. Run `scripts/recall_anchor_compiler_select.py` with explicit baseline
`V3_raw` and candidate `V3_anchor_raw` identities.

The selector thresholds are unchanged from preregistration 091:

1. accepted nonfallback typed records for at least 90 percent of eligible sessions;
2. deterministic whole session fallback for fewer than 10 percent of eligible sessions;
3. zero unsupported factual fields or entities, zero invalid spans, zero wrong profiles, and at
   least one audited record;
4. raw records retained for every eligible session;
5. candidate complete coverage at rank 100 greater than or equal to raw.

The selector also refuses replay, population, task, manifest, served identity, stored count, audit
count, or fallback count drift. Mean reciprocal rank, coverage at 10, characters, latency, record
mix, and token usage are descriptive and cannot override a failed gate.

## Predictions

1. At least 185 of 196 sessions receive accepted typed records.
2. No more than 10 sessions use whole session fallback.
3. The independent audit finds zero unsupported claims, zero invalid spans, and zero wrong profiles.
4. Replay, storage, and audit report the same unique compiled record count.
5. Candidate complete coverage at rank 100 does not decline against raw.
6. Mean reciprocal rank remains within 0.02 absolute of raw. This is descriptive, not an admission
   gate.

## Execution and stopping

Run only on fresh immutable VPS2 worktrees and a fresh output directory under
`results/aml-anchor-compiler-v3/`. Preflight exact commits, dependencies, provider presence,
schema, service version, host memory, load, OOM state, and absence of another embedding or indexing
worker. Never expose provider values.

Preserve every partial artifact. Never overwrite, resume, or silently rerun. A pure infrastructure
failure may receive a fresh immutable retry of this exact protocol after the apparatus is repaired.
A measured gate failure stops v3 and does not authorize M2 or M3. A complete pass authorizes only a
newly frozen v3 based multiview retrieval experiment, not the existing v2 preregistration 092 and
not an official AML run.

## Expected immutable artifacts

Write `V3_raw.json`, `V3_raw.service.log`, `V3_anchor_raw.json`,
`V3_anchor_raw.service.log`, `anchor_audit.json`, `selection.json`, `identity.json`, and
`SHA256SUMS` under one fresh run directory.

<!-- results are appended below this line; everything above is frozen -->

## Infrastructure result: pilot 97fdc2a8-38470a0a-pilot

Measured on 2026-09-19 from frozen RE-call commit
`97fdc2a8d160a559d78e496f49315d23d6116bb3` and AMB commit
`38470a0acbed8b21c679b104f640b4f671b4eed6`.

The raw arm completed. Its immutable `V3_raw.json` SHA-256 is
`275679a7e1c35f4fee15364a78027a13051be460e551b2bdd4d1e136efebab62`. The candidate arm then
stopped during Add when one request received HTTP 503. The service remained running, the host had
more than 22 GB available memory, and no OOM event occurred. No candidate JSON, independent audit,
or selector artifact exists, so this run has no admission verdict and cannot be scored.

The partial `V3_anchor_raw.service.log` is preserved with SHA-256
`2f3119be85f6e113534081d32b40498b9ce40360797b332f469017a28649723c`. It records successful
grounded compiler responses before the transient failure without recording request content.

## Infrastructure amendment: reproduce AML Add retry behavior

The public AML runtime contract measured on 2026-09-19 makes HTTP 503 retryable for Add, permits at
most 32 attempts, and requires the same `request_id` and payload for the logical write. The frozen
local client instead terminated on its first 503. The failed pilot therefore exercised a replay
transport mismatch rather than a registered compiler gate.

The repaired replay client retries only the documented Add HTTP status set, preserves identical
body bytes, uses at most 32 attempts, and applies deterministic exponential waits capped at 60
seconds. Permanent statuses still fail immediately. The regression node
`tests/test_recall_hosted_adapter.py::test_add_retries_a_transient_503_with_the_identical_logical_write`
was proven red against AMB commit `38470a0a`: the first 503 escaped after one attempt and failed its
explicit retry assertion. The same node must pass before a fresh immutable retry begins.

The registered population, arms, compiler treatment, gates, predictions, and stopping rule remain
unchanged. Every retry uses a fresh output directory and exact newly committed apparatus identity.

## Measured result: pilot 97fdc2a8-5b1cff30-pilot-r2

Measured on 2026-09-19 from frozen RE-call commit
`97fdc2a8d160a559d78e496f49315d23d6116bb3` and repaired AMB commit
`5b1cff3017e1180f56c43d3781569946ee5d9fc6`.

The fresh retry completed both arms, the independent audit, and the mechanical selector. The
checksum manifest verifies every expected artifact. Its `selection.json` SHA-256 is
`2e4b55d8b8fe8e4227ea431b56ee81943d9a476faf14fdc1a5eb7547204d9357` and its `identity.json`
SHA-256 is `194ec04a313e4347232fd0c2dcd5d0043051d022554091e1bf4769458dcb7675`.

Compiler v3 passed four of the five admission gates:

1. accepted typed records covered 194 of 196 eligible sessions, or `0.9897959184`;
2. two sessions used whole-session fallback, or `0.0102040816`;
3. the independent audit checked 1,230 compiled records and found zero unsupported claims, zero
   invalid spans, and zero wrong profiles;
4. raw records remained present for all 196 eligible sessions; and
5. candidate complete coverage at rank 100 declined from `0.9411764706` to `0.9117647059`, so the
   frozen rank-100 gate failed.

The single complete-coverage loss was `ts-golden-regen`. Mean reciprocal rank also declined from
`0.3217095592` to `0.2748844943`, a descriptive absolute change of `-0.0468250649`, so prediction
6 failed as well. Add p95 increased from `660.261 ms` to `20,973.655 ms`, while Search p95
increased from `388.225 ms` to `532.347 ms`.

The selector therefore chose `V3_raw`, set `admission_pass` and
`authorize_m2_m3_retrieval` to false, and stopped this lane. The result does not authorize the
draft M2/M3 retrieval experiment or any official AML run.

The useful result is narrower than rejection of typed memory. Compiler acceptance, grounding,
fallback, record accounting, and raw retention are now strong. The failure occurs when compiled
records compete with raw evidence inside the same bounded candidate and Top-K budget. A future,
separately preregistered experiment may use compiled retrieval only as a source-session sidecar
signal over an unchanged raw candidate membership. It must not reopen this measured arm or weaken
the rank-100 preservation gate.
