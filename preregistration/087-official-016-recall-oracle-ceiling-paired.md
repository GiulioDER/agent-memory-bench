# official-016: paired RE-call oracle ceiling on superseded tasks

Status: DRAFT until committed. The question, roster, evidence catalog, predictions and decision
rules above the results marker become frozen with the preregistration commit, before implementation
or any live participant session.

## Decision this experiment isolates

`official-013`, `official-014` and `official-015` did not establish that changing the initial
RE-call instruction improves task success. The remaining ambiguity is whether retrieval and prompt
execution are the bottleneck, or whether even the correct governing memory would fail to improve
these tasks under the frozen model and checker.

This experiment measures that ceiling. The control is the exact full-tools protocol used by
`official-012` through `official-015`. The treatment receives the exact current corpus-backed
memory bundle for its task in the system prompt before the participant starts. It receives no
memory MCP tools and performs no retrieval. This is a reference diagnostic, not a product arm.

The product decision is frozen before measurement:

1. At least three net oracle wins justify continuing toward a context-rich pre-mutation checkpoint.
2. Fewer than three net oracle wins stop the initial-skill and query-routing lane on this task set.
3. A positive oracle result does not validate automatic prefetch, a per-write hook or any specific
   retrieval implementation. It establishes only that correct memory has actionable headroom.

## Frozen evidence and roster

The run id will be `official-016-recall-oracle-ceiling-paired-superseded`.

The condition is `superseded`. The model is `deepseek/deepseek-v4-flash`. The seed values are
0 through 4. The namespace remains `amb-graph-rerank-official-010-superseded`. The participant,
checker, runner, network policy, provider policy, prices, corpus construction and concurrency are
held to the verified `official-015` apparatus.

The nine tasks are:

1. `ts-base36-id`
2. `ts-bom-merge`
3. `ts-golden-regen`
4. `ts-ignore-gen`
5. `ts-legacy-hash`
6. `ts-mig-name`
7. `ts-schema-additive`
8. `ts-semver-pin`
9. `ts-tz-utc`

`ts-natural-order` is excluded before measurement because the committed oracle catalog contains no
bundle for it. No new bundle will be authored for this run.

The selected catalog contains nine bundles and nine evidence items. Its canonical selected-catalog
SHA-256 is `322cd2331c8b1c6ed0e01eb293f6dd562088a016c6b31c25d304efe46ef5dad6`.
The source file `corpus/oracle_memory/bundles.jsonl` has SHA-256
`65592ceb95c07f00d5b4c9204b4b733875124034eff2fd4bdb903c32cf9629cb`.
Every selected item must remain an exact substring of a source whose digest matches the condition
corpus manifest.

## Arms

| Arm | Treatment |
|---|---|
| `recall_graph_fulltools_protocol` | Exact `official-012` control instruction and the same 22-tool RE-call surface |
| `oracle_memory` | Exact current task bundle plus the ordinary task static prompt, with no memory tools |

The control instruction is 3,924 UTF-8 bytes with SHA-256
`aae2f2cf6fe67cac3998b1692d9173ef9ae7edcbe3263053d36025e77f2dc7d8`.

The grid contains 9 tasks times 5 seeds times 2 arms, for 90 participant sessions and 90 checker
sessions. Arm order remains deterministically shuffled by the existing paired runner.

## Endpoints and analysis order

1. Apparatus validity: exact arms, roster, seed values, model, corpus fingerprint, selected catalog
   digest, bundle source validation, prompt digests, tool surfaces and isolation digests.
2. Primary outcome: paired checker success where both arms are admitted. Report oracle wins,
   control wins, double successes, double failures, net wins and the paired success difference.
3. Task-level headroom: paired outcomes by task, with special attention to tasks where the control
   fails while the oracle succeeds.
4. Application ceiling: oracle success, failure and wrong-fact application despite receiving the
   exact current bundle.
5. Control exposure: search rate, successful memory calls, tool errors and wrong-fact application.
6. Cost: input and output tokens, model turns, memory latency, wall time and estimated spend.
7. Reliability: discarded cells and reasons, participant errors, checker errors, silent retries and
   timeouts by arm.

No unpaired comparison will replace the paired primary endpoint. Historical runs are context only.

## Predictions frozen before implementation

1. The oracle will produce at least three net paired wins among the 45 possible paired cells. This
   is the minimum evidence of actionable headroom for the next architectural experiment.
2. The oracle success rate will exceed the control by at least 0.067, corresponding to at least
   three net wins if all 45 cells are admitted.
3. The oracle will apply zero superseded facts. Any oracle wrong-fact application fails the evidence
   packaging prediction even if task success improves.
4. Every admitted oracle session will carry one validated task bundle, no oracle session will expose
   a memory MCP tool, and every admitted control session will expose the frozen 22-tool surface.
5. The control search rate will be at least 0.80. A lower rate does not invalidate the oracle
   ceiling, but makes comparison with `official-012` through `official-015` operationally suspect.
6. The oracle will have no more participant errors or timeouts than the control because it removes
   the memory server from the participant path.
7. Oracle mean input tokens will not exceed control by more than 5 percent and oracle mean wall time
   will not exceed control by more than 10 percent on admitted paired cells.

## Gates and exclusions

The existing trusted challenge, admission, checker and adjudication rules remain authoritative. A
paired cell enters the primary analysis only when both arms are admitted. Missing records, failed
integrity checks, bundle digest mismatch, source mismatch, prompt mismatch, tool leakage or oracle
content leakage into the control discard the cell and are reported by arm and reason.

The result is not interpreted if fewer than 36 paired cells are admitted, if the selected catalog
digest differs, if the task roster differs, if the model differs, or if the oracle arm has memory
tools. The run is not silently continued under a replacement bundle or changed task roster.

The ceiling is considered absent for this task set if the oracle has fewer than three net wins. The
initial-skill lane remains stopped in that case even if the oracle reduces cost or wrong-fact rate.

<!-- results and append-only corrections go below this line; everything above is frozen -->
