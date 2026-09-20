# Preregistration 094: routed specialist five condition API evaluation

Status: frozen when committed. No live preparation, hosted ingestion, Search, participant model
session, or result analysis from this experiment may start before the commit that adds this record.

## Question

Does the routed specialist candidate preserve the proven Code4 coding behavior across all five AMB
memory conditions when the entire memory data plane is restricted to the public Add and Search API?

This is a private Agent Memory Benchmark evaluation. It is not the official Agent Memory
Leaderboard Smoke, an official evaluation, or a leaderboard submission. None of those actions is
authorized by this record.

## Architecture under test

The candidate keeps one logical corpus identity while storing heterogeneous vectors in physically
separate indexes:

1. Code4 is the conservative default and the coding route.
2. Context4 is selected only for explicit conversational memory queries without a code signal.
3. The retained `MM2_dual` implementation is selected only for image input or an explicit visual
   query. It preserves exact media and applies deterministic late rank fusion between the text and
   Voyage Multimodal 3.5 rankings.
4. Raw cosine scores from different embedding models are never compared, normalized together, or
   averaged. Fusion uses rank positions only.

The MemEye Brand v2 experiment retains its scientific `NO_GAIN` verdict. Its separate operational
decision selected `MM2_dual` because it had the strongest measured answer quality without reducing
Recall at 10 or Recall at 100. The five AMB conditions below contain coding text, not image memory,
so they can establish coding nonregression for an MM2 capable endpoint but cannot establish a
multimodal quality gain. A visual canary remains a mandatory preflight outside the scored grid.

## Embedding reuse without corpus leakage

The two hosted processes share a bounded, content addressed embedding cache. A cache identity binds
the complete registered embedding profile, vector dimension, encoder purpose, and exact input.
Context4 document vectors additionally bind the complete ordered document group and ordinal because
a contextualized vector is not a function of one chunk alone. MM2 keys bind canonical structured
input and keep document and query domains separate.

The cache reuses derived vectors only. Every condition retains its own user namespace, rows,
metadata, receipts, and Search scope. Cache reuse must not make one condition's memories searchable
from another condition. A miss still passes through the one shared VPS2 embedding lock. The cache is
an optimization and must not change ranking semantics.

## API boundary

Every hosted condition corpus is submitted through `/v1/add`. Every task receives evidence from
`/v1/search` using the exact task prompt. The harness performs no direct database insert, vector
write, internal retriever call, or MCP memory call. `/version` and `/v1/delete` are setup and cleanup
controls and are not memory operations available to the participant. The participant receives the
ordered Search result as a static task scoped evidence block, simulating the effect of the two
memory commands Add and Search.

## Systems and reference

The actual system arms remain:

| arm | treatment |
| --- | --- |
| `claude_md` | task specific static project bundle, no retrieved memory |
| `aml_c6_prefetch` | public API, frozen `C6_code4_exact_bm25` |
| `aml_c7_prefetch` | public API, `C7_routed_specialists` with the retained MM2 safeguards |

`claude_md` is the declared paired reference. The five names below are corpus conditions, not
additional retrieval implementations.

## Frozen condition order and task roster

Conditions run sequentially in this exact order:

1. `contradictory`, 10 tasks.
2. `present`, 27 tasks.
3. `adjacent`, 11 tasks.
4. `superseded`, 10 tasks.
5. `absent`, 11 tasks.

The condition runner derives the exact task ids from committed task declarations and the committed
retirement list. The frozen resolved roster is:

* `contradictory`: `ts-bom-merge,ts-dedup-order,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,ts-mig-name,ts-natural-order,ts-schema-additive,ts-semver-pin,ts-tz-utc`.
* `present`: `fa-dedup-key,ts-atomic-write,ts-base36-id,ts-bom-merge,ts-casefold-sort,ts-cli-exitcode,ts-config-layer,ts-crlf-export,ts-dedup-order,ts-empty-input,ts-golden-regen,ts-idempotent-run,ts-ignore-gen,ts-json-sorted,ts-legacy-hash,ts-log-mask,ts-manifest-rel,ts-mig-name,ts-natural-order,ts-nfc-count,ts-quote-shell,ts-retry-cap,ts-round-money,ts-schema-additive,ts-semver-pin,ts-stable-sort,ts-tz-utc`.
* `adjacent`: `ts-base36-id,ts-bom-merge,ts-dedup-order,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,ts-mig-name,ts-natural-order,ts-schema-additive,ts-semver-pin,ts-tz-utc`.
* `superseded`: `ts-base36-id,ts-bom-merge,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,ts-mig-name,ts-natural-order,ts-schema-additive,ts-semver-pin,ts-tz-utc`.
* `absent`: `ts-base36-id,ts-bom-merge,ts-dedup-order,ts-golden-regen,ts-ignore-gen,ts-legacy-hash,ts-mig-name,ts-natural-order,ts-schema-additive,ts-semver-pin,ts-tz-utc`.

There are 69 task condition cells per seed, three seeds, and three system arms, for 207 paired cells
and 621 participant sessions. Conditions are sequential. Within one condition, five task seed cells
may run concurrently. The three system arms of a cell continue to run together, so the maximum is
15 participant sessions in flight. Hosted Add concurrency remains three because provider calls are
serialized by the shared embedding lock.

## Frozen model and runtime

The answer model is `deepseek/deepseek-v4-flash` through the trusted capability broker. Session
timeout is 600 seconds. Corpus assembly seed is 1. Session seeds are 0, 1, and 2. Pricing remains
the preregistered 2026-08-22 DeepSeek Flash basis: input 0.0574 and output 0.1148 per million tokens.

The broker repair for an Anthropic beta query parameter must pass its mutation proved regression
test before model spend. The participant, checker, broker, egress proxy, source commit, image
digests, endpoint commits, cache identity, corpus manifests, preparation receipts, and qualification
receipt are recorded before the first participant session.

## Preconditions

1. The routed endpoint reports Code4 primary, Context4 specialist, Voyage Multimodal 3.5 profile
   `voyage-multimodal-3.5-v2`, the conservative router, rank fusion, shared embedding locking, and
   embedding cache enabled.
2. Shared chunk identity and metadata parity pass between Code4 and Context4.
3. A coding probe selects Code4, a conversational probe selects Context4, and a visual probe selects
   MM2. Each probe returns its planted evidence at the preregistered rank.
4. The corrected participant broker accepts `/v1/messages?beta=true` under a capability that allows
   `messages`, while unsigned and wrong scope requests remain refused.
5. A zero model preparation assembles all five conditions sequentially, ingests both hosted arms
   through Add, performs every distinct task Search, verifies nonempty ordered results, and records
   zero participant model sessions.

Any failed precondition blocks the full private run. It does not authorize a smaller favorable
subset.

## Endpoints

1. Primary: paired executable task success for C7 minus C6 over admitted cells, overall and by
   condition.
2. C6 and C7 task success relative to `claude_md`, overall and by condition.
3. Paired wins, ties, and losses by task condition cluster.
4. Damage, benefit, abstention, and planted wrong fact application by condition, using
   `claude_md` as the declared reference.
5. C6 versus C7 ordered Search identity and source recall on conditions where the governing source
   is present.
6. Route and embedding profile reported for every C7 Search.
7. Admission, discard, timeout, broker error, input tokens, output tokens, wall time, estimated
   model cost, Add latency, Search latency, and cache enabled status.
8. Condition namespace isolation and cleanup.

## Predictions

1. Every scored AMB prompt selects the C7 Code4 route. Context4 and MM2 remain inactive in the
   scored text grid.
2. C7 differs from C6 by no more than six successful cells in either direction over 207 paired
   cells.
3. C7 loses no more task condition clusters than it wins against C6.
4. C6 and C7 have identical ordered Search results for at least 90 percent of distinct condition
   task prompts. Differences remain permissible because cached vectors are float32 and fresh Voyage
   results are not byte deterministic.
5. Both hosted arms exceed `claude_md` success in `present`. No minimum uplift is predicted for an
   adversarial or absent condition.
6. C7 does not increase planted wrong fact application relative to C6 in `contradictory` or
   `superseded`.
7. At least 197 of 207 paired cells are admitted. A wiring failure discards the paired cell and is
   never converted into a task failure.
8. The shared cache is enabled on both endpoints, and the unit and live preflight evidence confirms
   reuse without a provider call for an exact Code4 passage, exact query, exact Context4 document
   group, and exact MM2 structured input.

## Decision rule

C7 remains the unified official candidate only if predictions 1, 2, 3, 6, and 7 pass. Prediction 5
is the usefulness gate for this private benchmark. Prediction 8 is an operational cost and
reproducibility gate, not a quality claim. The separate MemEye `NO_GAIN` verdict remains unchanged
regardless of this run.

No result from this record authorizes an official AML Smoke or official evaluation. Explicit user
approval remains required after the private result is reviewed.

## Frozen command shape

The exact immutable commits, image digests, endpoint URLs, credentials, and preparation receipt are
appended before live execution. The zero model preparation command shape is:

```powershell
$env:AMB_HOSTED_ADD_WORKERS='3'
$env:AMB_HOSTED_REQUEST_TIMEOUT_S='600'
python -m scripts.abstention `
  --prepare-only `
  --run-id specialist-conditions-001 `
  --namespace amb-specialist-conditions-001 `
  --conditions contradictory,present,adjacent,superseded,absent `
  --arms claude_md,aml_c6_prefetch,aml_c7_prefetch `
  --reference-arm claude_md `
  --seeds 3 `
  --seed 1 `
  --model deepseek/deepseek-v4-flash
```

The scored command shape, used only after the preparation receipts and all other preconditions
pass, is:

```powershell
$env:AMB_BLOCK_CONCURRENCY='5'
$env:AMB_HOSTED_ADD_WORKERS='3'
$env:AMB_HOSTED_REQUEST_TIMEOUT_S='600'
python -m scripts.abstention `
  --run-id specialist-conditions-001 `
  --namespace amb-specialist-conditions-001 `
  --conditions contradictory,present,adjacent,superseded,absent `
  --arms claude_md,aml_c6_prefetch,aml_c7_prefetch `
  --reference-arm claude_md `
  --seeds 3 `
  --seed 1 `
  --model deepseek/deepseek-v4-flash `
  --price-in 0.0574 --price-out 0.1148 --price-as-of 2026-08-22
```

<!-- results and append only corrections go below this line; everything above is frozen -->
