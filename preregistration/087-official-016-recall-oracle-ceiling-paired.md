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

## Results (2026-09-16)

The preregistered run completed all 90 participant sessions and all 90 checker evaluations. The
trusted setup and receipt verification passed. Of the 45 possible paired cells, 43 were admitted.
Two cells were discarded symmetrically from the paired endpoint because one participant record was
missing or unusable: `ts-base36-id` seed 4 in the oracle arm and `ts-tz-utc` seed 1 in the control
arm. The 43 admitted oracle records all carried one validated task bundle with the same frozen
catalog digest. The oracle exposed no memory tools and made no memory calls.

Two pre-measurement corrections were required. The first launch was refused before any participant
session because host location values contained literal quote characters. The next preflight exposed
that `--tasks` incorrectly reduced corpus construction from 206 to 205 session files. The harness
was corrected so task selection limits only the measured grid, while corpus construction continues
to use all 206 frozen session files. No participant session ran before either correction. The final
corpus fingerprint was
`5a090d3c0809f751b2b3f62a2eda5b666a50413e902594d7d7c983af0e0f3766`, identical to the frozen
comparison corpus.

### Primary paired outcome

| Outcome | Cells |
|---|---:|
| Both succeed | 27 |
| Oracle only succeeds | 15 |
| Control only succeeds | 1 |
| Both fail | 0 |
| Net oracle wins | +14 |

The control succeeded on 28 of 43 admitted cells, 65.1 percent. The oracle succeeded on 42 of 43,
97.7 percent. The paired success difference was +0.3256, or +32.6 percentage points. This exceeds
the preregistered minimum of three net wins by a wide margin.

Task-level oracle-only wins were distributed across seven tasks: four on `ts-base36-id`, three on
`ts-golden-regen`, one on `ts-ignore-gen`, two on `ts-legacy-hash`, two on `ts-mig-name`, two on
`ts-semver-pin`, and one on `ts-tz-utc`. The sole control-only result was on `ts-golden-regen`.

### Safety, exposure, cost and reliability

The oracle applied zero wrong facts. The control applied a wrong fact in 3 of 43 admitted cells,
7.0 percent. Control searched in 39 of 43 admitted cells, 90.7 percent, and in 41 of all 45 control
sessions, 91.1 percent. Its maximum observed memory call count was three. The oracle made zero
memory calls by construction.

The full run consumed 6,435,745 tokens and an estimated $0.3813. The oracle used 1,077,566 tokens
and $0.0669, versus 5,358,179 tokens and $0.3144 for the control. Across all sessions, mean input
tokens were 21,973.7 for oracle and 116,427.7 for control; mean wall time was 65.7 seconds for oracle
and 95.7 seconds for control. Each arm had one participant error, so the oracle was not less
reliable than the control on the preregistered criterion.

### Frozen prediction disposition

| Prediction | Result |
|---|---|
| At least three net paired oracle wins | Passed: +14 |
| Oracle success advantage at least 0.067 | Passed: +0.3256 |
| Zero oracle superseded-fact applications | Passed: zero wrong facts |
| Validated bundle, no oracle tools, frozen control surface | Passed |
| Control search rate at least 0.80 | Passed: 0.907 admitted |
| Oracle participant errors or timeouts no greater than control | Passed: one participant error per arm |
| Oracle token and wall-time ceilings | Passed |

### Decision

The ceiling is present and large. Correct task-specific memory materially improves task success,
eliminates observed wrong-fact application, and reduces cost when delivered outside the autonomous
search path. The next experiment should therefore leave the general initial-skill lane stopped and
test an architectural bridge that retrieves and injects context-rich evidence before the first
repository mutation. It should isolate whether a pre-mutation checkpoint can recover a meaningful
fraction of the oracle gain without granting the treatment oracle bundle selection.
