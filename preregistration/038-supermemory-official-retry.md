# 038: Supermemory official retry

Status: FROZEN before the retry measurement.

## Question

Does the pinned Supermemory Claude Code integration improve execution graded task success over the
same `bare` control on the frozen AMB official grid, while remaining within the five hour wall time
limit?

## Retry identity and preservation

This is a new additive retry with run id `supermemory-002`. It preserves every artifact from
`supermemory-001` unchanged. The earlier run is not resumed because its completed `absent` artifact
was admitted without the lifecycle evidence required by the corrected executor. The retry fixes
full-run adapter environment propagation and carries the Supermemory config digest and hook ledger
into each final record.

## Submission design

The retry is an additive submission to the frozen `official-003` leaderboard base. It does not
replace or rerun the base arms. The measured roster is exactly `bare,supermemory`; no Recall arm is
included. The result will be joined to `official-003` by `(task_id, seed, condition)` and generated
by `scripts/build_arm_submission.py` from the published Supermemory records.

The model is `deepseek/deepseek-v4-flash`, the instruction variant is `protocol`, the corpus
condition assembly seed is 1, and the session seed count is 5. All five conditions are run:
`absent`, `superseded`, `contradictory`, `adjacent`, and `present`.

The current selection resolves to 73 task condition cells per session seed, 365 cells per arm, and
730 sessions across the two arms. The run uses the repository launcher on VPS2 with bounded block
concurrency 2. Prices are fixed at 0.0574 USD per million input tokens and 0.1148 USD per million
output tokens, as of 2026-08-22.

## Explicit Supermemory benchmark configuration

Supermemory Local remains pinned at version 0.0.8, and the official plugin remains pinned at commit
`e6227edc4f33b83317cfde2e7cd9790c794d22d1`. The adapter uses the vendor supported
`maxProfileItems` setting with `SUPERMEMORY_BENCHMARK_MAX_PROFILE_ITEMS=0`. This prevents the
plugin's startup profile hook from injecting five full transcript memories into the model context;
prompt-time lifecycle recall remains enabled and is recorded by the required hooks. The setting is
written into each isolated Claude config and included in its config digest.

The direct static-memory write path preserves each rendered transcript while splitting only above
30,000 characters, then submits two batches of 20 memories concurrently and permits
each local batch request up to 180 seconds for Supermemory Local's bounded two-worker embedding
queue. Memory contents and metadata are unchanged; this is a transport-performance fix required
to keep the official run within the five hour limit.

## Prediction and gates

I predict that the Supermemory arm will ingest the complete frozen condition feed, pass its
SessionStart and UserPromptSubmit lifecycle admission checks, and produce a positive or null delta
against `bare`. I predict that every condition will produce ordinary records, streams, costs and
admission artifacts, and that the complete retry will finish in less than 18,000 seconds.

The result is eligible for additive leaderboard construction only if the adapter review record,
this preregistration, full artifacts, per condition verification, base join, search rate floor, and
timing limit all pass. A timeout is an outcome, not a wiring failure, and is not retried.

<!-- results are appended below this line; the prediction above is never edited -->
