# Preregistration 091: RE-call anchor compiler v2 admission pilot

Status: frozen before any provider backed replay under this protocol.

Date frozen: 2026-09-19.

This is a local development experiment. It does not authorize an official AML Smoke or Full run.
The registered section ends at the results marker near the bottom. Measured results may be appended
below that marker without editing anything above it.

## Question

Can a source grounded compiler produce usable typed coding records for at least 90 percent of the
frozen historical sessions without unsupported claims, excessive whole session fallback, or loss
of complete evidence coverage at rank 100?

This pilot tests admission and retrieval preservation only. It does not test executable Task Solve
and cannot promote repository knowledge, engineering experience, routing, or an AML submission.

## Frozen population

Use the committed `corpus/manifest.json` containing 196 historical sessions and all 34 committed
retrieval tasks. The manifest SHA-256 at freeze time is
`58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`.

Both arms receive byte identical sessions in manifest order. Search receives only each committed
task prompt, exact `user_id`, and Top K 100. Fact terms, checker data, task answers, and retrieval
labels are used only after Search for scoring. Each task is captured once. No coding agent runs.

## Arms

1. `V2_raw`: raw dense plus exact lexical storage and retrieval.
2. `V2_anchor_raw`: the identical raw path plus compiler v2 typed records.

The arms use the same frozen RE-call commit, AMB commit, embedding identity, retrieval profile,
candidate width, RRF constant, task set, corpus, provider identities, and dependency locks. They
use separate run specific `user_id` namespaces inside the same dedicated table and generation.

## Compiler v2 mechanism

1. RE-call deterministically splits stored messages into bounded overlapping excerpts.
2. Every excerpt receives a content bound identifier derived locally from the exact session,
   message ordinal, start, end, and source bytes.
3. Exact paths, files, exceptions, configuration names, symbols, and commands are extracted
   locally and supplied as anchor metadata.
4. `openai/gpt-4o-mini` may choose supplied anchor identifiers and a record type. It may not
   generate source offsets or anchor identifiers.
5. RE-call resolves selected anchors locally into exact source spans.
6. Every nonempty factual field and entity must be an exact substring of a selected anchor.
   Unsupported fields are removed independently. If every proposed factual field is removed,
   RE-call retains the valid type and selected evidence with one bounded verbatim field.
7. An unknown anchor identifier, wrong session identifier, malformed response, provider failure,
   or zero accepted record triggers the existing deterministic whole session fallback. Accepted
   records carry profile `anchor-v2`; fallback records carry profile `deterministic-fallback` and
   cannot count as typed acceptance.
8. Raw history is stored in both arms and can never be removed by compiler output.

Maximum compiler attempts remain three. Each attempt has a 12 second request timeout. The model,
prompt digest, attempts, fallback count, accepted record count, removed field count, selected
anchor integrity, token use, and served commit are recorded without logging source conversation
text or credentials.

## Independent source audit

After `V2_anchor_raw` ingestion, `scripts/recall_anchor_compiler_audit.py` reads the stored records
and the original committed corpus independently of the compiler. For every compiled record it:

1. resolves each stored message ordinal and character range against original source bytes;
2. verifies the stored quote equals the exact source slice;
3. verifies every nonempty task, problem, action, outcome, validation, and entity value occurs in
   at least one independently validated span;
4. verifies every nonempty event timestamp occurs on a source message;
5. verifies the stored source session identifier equals the committed corpus session;
6. verifies accepted records use `anchor-v2` and fallback records use
   `deterministic-fallback`;
7. counts sessions with raw records, accepted typed records, and deterministic fallbacks.

The audit publishes only aggregate counters, record identifiers, hashed session identifiers, and
issue codes. It publishes no conversation text, credentials, prompts, or provider responses.

## Frozen gates

The mechanical selector authorizes later M2 and M3 retrieval preregistrations only if every gate
passes:

1. **Typed session acceptance:** at least one accepted nonfallback typed record exists for at
   least 90 percent of eligible sessions.
2. **Whole session fallback:** fewer than 10 percent of eligible sessions use compiler fallback.
3. **Source grounding:** the independent audit finds zero unsupported factual fields or entities,
   zero invalid spans, zero wrong compiler profiles, and at least one audited record.
4. **Raw rescue:** every eligible session retains raw records.
5. **Rank 100 preservation:** `V2_anchor_raw` complete coverage at 100 is greater than or equal to
   `V2_raw` on the identical 34 task retrieval set.

The boundary values are literal: 90 percent acceptance passes; 10 percent fallback fails. Mean
reciprocal rank, coverage at 10, returned characters, Add latency, Search latency, record type mix,
and token cost are descriptive and cannot override a failed gate.

## Mechanical selection

Run `scripts/recall_anchor_compiler_select.py` on exactly one `V2_raw` replay, one
`V2_anchor_raw` replay, and one independent audit. The selector refuses population, task,
manifest, served product, schema, or counter drift. It records SHA-256 for all three inputs.

If all gates pass, the next work is to freeze independent M2 repository knowledge and M3
engineering experience retrieval experiments against the raw baseline. It does not authorize
combining views, task routing, executable cells, confirmation, robustness, or an official run.

If any gate fails, retain raw, stop this compiler lane, preserve all artifacts, and diagnose the
failed gate without changing thresholds or replaying into an existing directory.

## Execution and safety

Run only on the dedicated immutable VPS2 worktrees. Use user scoped systemd with linger enabled.
Preflight the Voyage and OpenRouter dependencies, exact git commits, dependency locks, schema,
service version payload, and immutable output path before ingestion. Never print or copy provider
keys. Preserve partial artifacts and privacy safe service logs.

Do not run concurrently with another embedding or indexing job. Stop on a new OOM event, unsafe
host memory, corpus or identity drift, provider authentication failure, or a service response that
cannot prove request identity. An infrastructure failure authorizes only a fresh immutable retry
of the identical frozen protocol after repairing the apparatus.

## Predictions

1. At least 177 of 196 eligible sessions receive accepted typed records.
2. Fewer than 20 of 196 sessions use whole session fallback.
3. The independent audit finds zero unsupported claims and zero invalid spans.
4. Complete coverage at 100 does not decline against raw.
5. The candidate improves mean reciprocal rank, but this is descriptive and not a gate.

## Expected immutable artifacts

Write new files only under
`results/aml-anchor-compiler-v2/<recall-short>-<amb-short>-pilot/`:

1. `V2_raw.json` and its privacy safe service log;
2. `V2_anchor_raw.json` and its privacy safe service log;
3. `anchor_audit.json`;
4. `selection.json`;
5. `SHA256SUMS` and a frozen identity manifest.

Existing paths cause refusal. No artifact is overwritten, resumed, or repaired in place.

<!-- results are appended below this line; everything above is frozen -->
