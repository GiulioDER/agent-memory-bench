# Preregistration 093: routed specialist full AMB Task Solve

Status: frozen when committed. No session from this run may start before the commit that adds
this record.

## Question

Does the routed C7 specialist corpus preserve the full Code4 coding result while making Context4
and Multimodal 3.5 available in isolated indexes for future noncoding routes?

This run measures final executable task success. It compares the proven C6 Code4 retrieval system
with C7 through the same public AML Add and Search contract. It is not an official AML Smoke and
does not authorize any official AML evaluation.

## Frozen implementations

The RE-call candidate is commit `2098a903520dd5802e58838971bcb02ed9509bb2`.
Its core routed specialist implementation was committed as
`3cc8f9a1ba0beb57239b131568fec9eece97defb`.

The AMB hosted prefetch apparatus is commit
`b80b45ceb0d5a0628eb4f7bc4211f12a273b9163`.

The two hosted arms are:

| arm | required endpoint variant | retrieval |
| --- | --- | --- |
| `aml_c6_prefetch` | `C6_code4_exact_bm25` | Code4 exact dense plus canonical BM25, RRF constant 60 |
| `aml_c7_prefetch` | `C7_routed_specialists` | conservative route, then the selected specialist plus lexical or visual rank fusion |

Both arms delete only their dedicated run namespace, ingest the same committed corpus through
public `/v1/add`, search with the exact task prompt through public `/v1/search`, preserve returned
rank order, and inject the first 10 evidence items into the task system prompt. They do not expose
a memory tool to the agent. This is deliberate because the official coding evaluation supplies
the task and memory to the system. The run measures retrieval plus evidence use, not autonomous
query formulation.

The designated control is `claude_md`, using the same task specific static repository bundle and
no memory evidence.

## Frozen corpus, tasks, and grid

The corpus is `corpus/manifest.json`, SHA 256
`58055df1828b2c1e51bc3c7f9f82e916145c67aa58332f22ce1b86b2d849b814`, containing 196 sessions.

All 34 executable AMB tasks run. The exact roster is:

`fa-dedup-key,ts-append-only,ts-atomic-write,ts-base36-id,ts-bom-merge,ts-bool-env,ts-casefold-sort,ts-cli-exitcode,ts-config-layer,ts-crlf-export,ts-csv-quote,ts-dedup-order,ts-empty-input,ts-glob-hidden,ts-golden-regen,ts-idempotent-run,ts-ignore-gen,ts-json-sorted,ts-legacy-hash,ts-log-mask,ts-manifest-rel,ts-mig-name,ts-natural-order,ts-nfc-count,ts-quote-shell,ts-retry-cap,ts-round-money,ts-schema-additive,ts-semver-pin,ts-stable-sort,ts-tz-utc,xs-evolve-lease,xs-join-batch,xs-widen-manifest`.

The three `xs-*` tasks are admitted only through the explicit `--include-synthesis` flag. This
does not change AMB's historical default grid, and synthesis tasks are forbidden with a mutated
condition corpus.

There are three arms, 34 tasks, and three seeds, for 102 paired cells and 306 sessions. The model
is `deepseek/deepseek-v4-flash`. Timeout is 600 seconds. The base relevant plus noisy corpus is
used with no adversarial condition mutation. Block concurrency is three. Hosted Add concurrency
is three.

## Qualification gate before model spend

The RE-call routed specialist qualification must pass every gate in
`docs/preregistrations/2026-09-20-aml-routed-specialist-corpus.md` before any Task Solve session.

The AMB dry run must resolve exactly 306 sessions and all 34 task ids. Both endpoints must expose
the required variant and pass ingestion. Every task must produce a nonempty Search response for
both hosted arms. Any endpoint mismatch, missing task prompt, shared prompt refusal, corpus hash
mismatch, or ingestion error blocks the run.

## Endpoints

The primary endpoint is paired executable task success for C7 minus C6 across 102 cells.

Secondary endpoints are:

1. Task success for each hosted arm minus `claude_md`.
2. Per task paired wins, ties, and losses for C7 against C6.
3. C6 and C7 source session recall at 10 from the saved Search payloads.
4. The number of tasks whose ordered injected evidence differs between C6 and C7.
5. Admission rate, discarded cells, timeout rate, input and output tokens, wall time, and estimated
   cost by arm.
6. The three synthesis task verdicts reported individually. They remain diagnostic because there
   is only one task per synthesis shape.

## Predictions

1. Every one of the 34 exact task prompts selects the C7 code route during qualification.
2. C7 task success differs from C6 by no more than three cells in either direction over 102 paired
   cells.
3. C7 loses no more task clusters than it wins against C6.
4. Both hosted arms retrieve at least one relevant source session in the first 10 results for all
   34 tasks.
5. Ordered injected evidence differs for no more than five tasks. Small differences are permitted
   because fresh Voyage query vectors are not byte deterministic.
6. Both hosted arms exceed `claude_md` task success by at least five percentage points.
7. At least 97 of 102 cells are admitted. A wiring discard in either hosted arm discards the paired
   cell and is reported, never converted into a task failure.
8. C7 median Search latency is no more than 1.25 times C6 median Search latency on coding prompts.
   Add latency is reported separately because C7 intentionally writes two text indexes.
9. The synthesis tasks do not support a product ranking. Their per task outcomes are reported as
   mechanism diagnostics only.

## Decision rules

C7 passes the coding nonregression gate only if predictions 2, 3, 4, and 7 pass. Prediction 6 is
the usefulness gate for using hosted prefetch as evidence about final task quality. If prediction
6 fails, C6 versus C7 remains a valid nonregression comparison but does not show that either
memory treatment helped.

A pass licenses keeping C7 as the unified candidate architecture while preserving Code4 as the
coding route. It does not license equal Code4 plus Context4 fusion, a multimodal quality claim,
an official AML Smoke, or an official AML evaluation.

## Frozen command

The run uses the existing trusted model broker and the following runner arguments. Secrets and
broker addresses remain environment supplied and are never written to results.

```powershell
$env:AMB_BLOCK_CONCURRENCY='3'
$env:AMB_HOSTED_ADD_WORKERS='3'
python -m scripts.pilot `
  --run-id specialist-full-001 `
  --namespace amb-specialist-full-001 `
  --arms claude_md,aml_c6_prefetch,aml_c7_prefetch `
  --tasks fa-dedup-key,ts-append-only,ts-atomic-write,ts-base36-id,ts-bom-merge,ts-bool-env,ts-casefold-sort,ts-cli-exitcode,ts-config-layer,ts-crlf-export,ts-csv-quote,ts-dedup-order,ts-empty-input,ts-glob-hidden,ts-golden-regen,ts-idempotent-run,ts-ignore-gen,ts-json-sorted,ts-legacy-hash,ts-log-mask,ts-manifest-rel,ts-mig-name,ts-natural-order,ts-nfc-count,ts-quote-shell,ts-retry-cap,ts-round-money,ts-schema-additive,ts-semver-pin,ts-stable-sort,ts-tz-utc,xs-evolve-lease,xs-join-batch,xs-widen-manifest `
  --include-synthesis `
  --seeds 3 `
  --model deepseek/deepseek-v4-flash `
  --timeout 600 `
  --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

Retries are permitted only for a documented wiring failure before a scored outcome. Task failure,
timeout, or an unfavorable result is never retried.

<!-- results and append only corrections go below this line; everything above is frozen -->

## Append only safety apparatus amendment, before live calls

No live hosted call or model session had run when this amendment was written. Apparatus commit
`df67fcf0` adds three fail closed controls without changing the frozen task roster, arms, prompts,
model, seeds, endpoints, or predictions:

1. C6 and C7 use endpoint specific credentials named `RECALL_AML_C6_API_KEY` and
   `RECALL_AML_C7_API_KEY`. A legacy shared key may fill one missing side only when it is byte
   equal to the other side's explicit key.
2. An empty hosted Search is a setup failure and cannot become an empty prompt or a scored model
   session.
3. The frozen command is first run with `--prepare-only`. That mode ingests both hosted arms,
   searches each of the 34 distinct prompts once per arm, writes a nonoverwriting preparation
   receipt with 68 searches and `model_sessions_launched: 0`, then returns before broker,
   adjudication, or task runner construction.

The full 306 session command remains the frozen command above. It may start only after the
preparation receipt passes and the separate RE-call nine gate qualification passes. This
amendment does not authorize an official AML Smoke or official AML evaluation.

### Preparation provenance correction, before model spend

The first zero session preparation completed both ingestions and all 68 nonempty Searches, but
its `corpus_manifest_sha256` field was mislabeled: it contained the normalized session mapping
digest rather than the frozen manifest file SHA 256. It launched zero model sessions. Commit
`ba60e204` records both values separately and restores the file digest to the manifest field. A
new preparation receipt from that commit or a direct descendant is required before Task Solve.
