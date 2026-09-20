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

## Frozen execution manifest before preparation

The preparation uses these immutable inputs:

* AMB implementation commit: `32d1214874dbc6567af6be314e60ac6f115d0a5d`. Later append only
  evidence commits do not change executable harness code.
* RE-call commit: `28ed55c77928f3526f0c2c52ffc5d32dce0b7303`.
* Participant image: `sha256:698458737825cf2586e44ae7188093979afff1950599f957bc7a8bd1edf9ba73`.
* Checker image: `sha256:4f3696c7511979164cdf23828c066dad90878859a783db80ecc5bbf63f6a2079`.
* Runner image: `sha256:f9160a82ca0a0acbe4a6729977f7a4f37244eb15e151160537b7285548d6532d`.
* Model broker image: `sha256:ee9864c6a5ab7f846cb3a0a80f0c74bc508a3e2580506106f720a18a7404f266`.
* Egress proxy image: `sha256:8484e02e54f3e2648b504f2f4f1e87025ee714b608324e252cc9cec3c17e905b`.
* Network policy: `sha256:1c525e95987ba6d234eeeac53c355b7114ec1b48a4e41d37275e4b8d8db8e0ef`.
* Oracle version: `sha256:abb63a2e9259db22927b0c4c55c9db9bb9a7d691543bf69671daf2dc5fb3c83b`.
* C6 endpoint: private loopback port 18009, dedicated credential.
* C7 endpoint: private loopback port 18008, distinct dedicated credential.

The rebuilt model broker artifact accepted `/v1/messages?beta=true` with a signed `messages`
capability and refused both a wrong method and an unsigned token with HTTP 403. The private C6
versus C7 qualification passed all nine gates, including exact top 100 parity on all 34 coding
queries and rank 1 Code4, Context4, and MM2 canaries. It recorded
`official_aml_launched: false`.

## Preparation 001 observability refusal

Preparation `specialist-conditions-001` completed all five conditions sequentially, wrote 138
nonempty hosted Search artifacts with 10 hits each, and launched zero model sessions. It is not
eligible to authorize the scored run because the public Search response omitted the selected
specialist route and embedding profile headers. The service had verified Code4 internally during
qualification, but the AMB artifacts could not independently prove prediction 1 for every task.

The receipts and work directories are retained as zero model diagnostic evidence. RE-call commit
`4334084d13e38d02d881b2207c85152858e608d9` adds
`X-Recall-Specialist-Route` and `X-Recall-Specialist-Embedding-Profile`. A mutation proved HTTP
regression test failed with the pre-repair `KeyError` and passes after the repair. Qualification
and all five preparation conditions must be repeated at that commit under a new run id before any
participant model session.

## Preparation 002 passed

Preparation `specialist-conditions-002` repeated all five conditions sequentially against RE-call
commit `4334084d13e38d02d881b2207c85152858e608d9` and launched zero model sessions. It recorded
69 task prompts, 138 nonempty hosted Search artifacts, and 10 hits for every Search. Every C7
artifact reported route `code`, embedding profile `voyage-code-4-v1`, variant
`C7_routed_specialists`, and the exact served commit. C6 and C7 had identical ordered result
payload hashes for all 69 prompts.

The preparation receipt SHA256 values are:

* `contradictory`: `fb391abf62e52767eaa6150d3907e7acc9958a0538bac156be114e42c3b4a3c2`.
* `present`: `4a135991585ca03d65778c2940e01aac8bc6d48c15d24f74a11ad3bacca0f87a`.
* `adjacent`: `c8c32a0d48d7d7ce0bdf6b675fb62e45455107e8fcdc2ec6a2df231218e11d7a`.
* `superseded`: `3fe17173c5dc5f811026c1a334b55d62d850d1025f3ffb96cb428be046f55198`.
* `absent`: `ecfd17a9d9e24d2c8c84c9b538f68a96717939a6a971902e7a9f9cad60cf524e`.

The shared cache held 3,028 vectors after preparation. Repeated Add latency stayed between 6.5 and
11.3 seconds per hosted arm and condition. This is operational evidence only; provider call count
remains unmeasured. All frozen preconditions are satisfied for the private scored run. This does
not authorize an official AML Smoke or official evaluation.

The private scored run uses run id `specialist-conditions-002` and namespace
`amb-specialist-conditions-002`, matching the valid preparation receipts. This is an operational
correction to the frozen command example because the `001` preparation is retained as refused
diagnostic evidence. It changes no condition, task, system arm, seed, model, price, concurrency,
endpoint, or decision rule.

## Scored attempt 1 data policy gate

The first scored launch stopped during the `contradictory` setup, after both hosted Add operations
and before any participant model session, because `AMB_DATA_POLICY_FILE` was unset. The partial
condition contains only the trusted challenge and initial execution event. It has no participant
record, model token, score, or adjudication receipt.

This is a wiring failure under the frozen zero-model retry rule. The retry supplies the existing
synthetic-only provider policy file already used by the private benchmark host. It changes no
condition, corpus, task, system arm, model, seed, price, concurrency, endpoint, prediction, or
decision rule. The partial result, work directory, log, and pid record are preserved under an
attempt 1 data policy archive name.

## Scored attempt 2 checker mount refusal

The second scored launch completed all 90 `contradictory` participant sessions and began
`present`, but its scores are invalid and must not be analyzed as model outcomes. Every one of the
90 contradictory checker verdicts failed because the production launchers passed
`task.oracle_dir.parent` to the isolated checker. The worker mounts that directory at `/oracle`,
while each bundled checker reads its task-specific files directly below `/oracle`. The recorded
verdicts therefore contain missing paths such as `/oracle/data`, `/oracle/as_of.txt`, and
`/oracle/catalog.json`.

This is systematic infrastructure failure, not a zero score. On the exact same 10 tasks and seeds
0 through 2, official run 003 scored `claude_md` at 23 of 30 and `recall_prefetch` at 19 of 30.
The invalid run's participants also produced apparently correct deliverables in sampled private
records before the checker failed. The controller and its child runner were terminated as soon as
the fault was established, and 12 current-run participant containers left by the interruption were
removed. Unrelated long-running containers were not touched.

The hosted memory path itself passed its audit. Both C6 and C7 recorded 10 nonempty Search hits for
all 10 contradictory task prompts and `prefetch_status=ok` for all 30 sessions per hosted arm. The
ranked prompt files exist and their hashes match the session records. Every C7 Search reported
route `code`, profile `voyage-code-4-v1`, variant `C7_routed_specialists`, and served commit
`4334084d13e38d02d881b2207c85152858e608d9`. C6 and C7 result hashes were identical for all 10
prompts, which is consistent with the preregistered prediction that this coding grid uses Code4 in
both arms. A zero in-session memory-call count is expected for these harness-prefetch arms and is
not evidence that Search was skipped.

AMB commit `4aa0a394e5fb9295ca92aad517251ba760eb253d` changes both production call sites to pass the exact
task oracle directory. Its new regression test failed against the pre-repair `.oracle_dir.parent`
calls and passed after the repair; the full isolation test file passed with four workers, 20 passed
and 2 skipped.

The invalid `specialist-conditions-002` scored artifacts are retained only as refusal and wiring
evidence. They cannot be resumed or combined with a valid result. Any retry uses a new run id and
namespace, `specialist-conditions-003` and `amb-specialist-conditions-003`, and first repeats the
zero-model five-condition preparation. Before any participant session, a real isolated-checker
canary must grade an informed reference successfully with the pinned checker image. This correction
changes no condition, corpus, task, arm, seed, model, price, concurrency, endpoint, prediction, or
decision rule. It does not authorize an official AML Smoke or official evaluation.

## Private checker repair smoke passed

Before preparing run `003`, the repaired checkout passed two private checks with the pinned checker
image. A zero-model canary applied the committed informed reference for `ts-bom-merge` and received
the expected checker verdict, `5 rows merged, BOM header handled`. A separate one-task, one-seed,
three-arm DeepSeek Flash smoke then completed three participant sessions through the specialist
model broker.

The smoke admitted its one paired cell with zero discards. C6 and C7 each returned 10 hosted Search
hits, recorded `prefetch_status=ok`, injected a prompt whose hash was bound into the private record,
and passed the repaired checker. C7 reported route `code`, embedding profile
`voyage-code-4-v1`, variant `C7_routed_specialists`, and served commit
`4334084d13e38d02d881b2207c85152858e608d9`. C6 and C7 had the same ordered result hash and each
scored 1 of 1. The `claude_md` session scored 0 of 1 for a real task failure involving the BOM
header, not an infrastructure error.

The smoke's adjudication receipt verified, the run verifier passed every applicable check, and the
artifact recorded 75,067 total tokens with an estimated model spend of $0.0046. No HTTP
authorization, provider, participant, or checker infrastructure failure occurred. This was a
private AMB smoke named `specialist-fusion-smoke-001`; it was not the official AML Smoke and grants
no authorization for one.

## Preparation 003 passed after checker repair

Preparation `specialist-conditions-003` ran all five conditions sequentially at AMB commit
`95fb6b6688661968cc424849817734e38b16f9c1` and launched zero model sessions. It recorded 138
nonempty Search artifacts across 69 distinct condition-task prompts, with 10 hits in every
artifact. All 69 C6/C7 ordered result payload hashes were identical. Every C7 Search reported
route `code`, embedding profile `voyage-code-4-v1`, variant `C7_routed_specialists`, and served
commit `4334084d13e38d02d881b2207c85152858e608d9`.

The preparation receipt SHA256 values are:

* `contradictory`: `dec7fd404aa0907bb069b087071420af3785fa1cedef7a297da64c5cb39156dd`.
* `present`: `6270dcbf3d68a263fcc552356ac7a5a56517c3d05fc2feb127c90caa805ad071`.
* `adjacent`: `d09b1c05ab98e5998dd91096517874ff4c3617a4ed18e6b92c06a770b7960498`.
* `superseded`: `59e5274339c9587d496642028ac92ff1cccfde40e274d9241ffbfbac8375f407`.
* `absent`: `097ac8106107a09409d462a197df80f4b7019cbe31244b703d32c474db18f44d`.

The eligible private scored run uses run id `specialist-conditions-003` and namespace
`amb-specialist-conditions-003`. All other frozen parameters remain unchanged. This preparation
does not authorize an official AML Smoke or official evaluation.
