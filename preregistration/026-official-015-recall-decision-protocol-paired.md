# official-015: paired compact RE-call decision protocol

Status: DRAFT until committed. The question, exact treatment, endpoints, predictions and analysis
rules above the results marker become frozen with the preregistration commit, before implementation
and before any participant session.

## Decision this experiment isolates

The experiment asks whether a short executable decision protocol improves agent quality by making
RE-call use sequential and unambiguous:

1. one mandatory `recall_search` before every other tool;
2. one frozen query construction template for unknown hazards;
3. explicit field precedence and evidence authority;
4. one graph escalation only for a real conflict;
5. no more than two RE-call calls in the complete session.

This is a whole-skill comparison. It does not claim to isolate prompt length, first-tool choice,
query construction and result interpretation from one another. The product question is whether the
compiled protocol is better than the exact `official-012` graph-first protocol while every other
experimental input is held fixed.

## What official-014 established

The following values were measured on 2026-09-16 from the final public records and private streams
of `official-014`. They can be recomputed with:

```text
PYTHONUTF8=1 python -m scripts.verify_run results/official-014-recall-graph-quality-gate-paired-superseded
jq . results/official-014-recall-graph-quality-gate-paired-endpoints.json
jq . results/official-014-recall-graph-quality-gate-paired-superseded/{admission,costs}.json
```

The paired run admitted 45 of 50 cells. Control and treatment both succeeded in 33 of 45, with five
treatment wins, five control wins, 28 double successes and seven double failures. The treatment
reduced admitted search exposure from 39 of 45 to 33 of 45, increased incomplete sessions from one
to four, increased mean input tokens from 125,340 to 131,889, and increased mean wall time from
101.1 to 122.4 seconds. Wrong-fact application moved from one case to zero, which is directionally
useful but does not rescue the null primary outcome.

The mechanism analysis found four failures.

1. The 1,257 byte appendix raised the instruction from 3,924 to 5,182 bytes. Both arms made 53
   admitted graph calls, but the treatment concentrated them in fewer sessions. Its admitted
   maximum was 14 memory calls; one incomplete treatment session made 32.
2. The operation-and-hazard prose did not change initial query construction. Across all sessions,
   only five of 43 control first graph queries and two of 37 treatment first graph queries contained
   a frozen risk lexeme such as failure, hazard, error, conflict, stale or superseded.
3. `recall_reasoning_query` can return `outcome=abstained` and
   `refusal_reason=no_answer_provider` while `trusted_evidence.decision_state=supported` and trusted
   items are populated. Participants sometimes interpreted answer-provider abstention as retrieval
   abstention and discounted the evidence.
4. Retrieved items can mix explicit user-approved decisions, factual history, assistant
   recommendations and distractors. The quality gate did not define an authority order. On
   `ts-base36-id`, the correct explicit decision was retrieved, but both arms scored zero of five.

These observations are descriptive diagnostics, not new endpoints selected after seeing the next
run.

## Exact frozen treatment

The treatment instruction is exactly the text inside this block, without the fence and with one
terminal newline:

```text
# RE-call decision protocol

Before any other tool, call `mcp__recall__recall_search` exactly once.

Construct its query as:
`<artifact or operation>; prior failure, hazard, constraint, decision, superseded`

Do not merely repeat the task goal. Name the concrete operation or artifact and include at least
one risk term even when you do not know which hazard exists.

Read the result in this order:

1. `trust_state`: unavailable or degraded means memory did not establish evidence.
2. `decision_state` and `abstained`: when supported, inspect every hit, not only the first.
3. Evidence authority: an explicit user-approved decision such as `Decision`, `Agreed` or an
   accepted correction outranks factual history; factual history outranks an assistant
   recommendation; a related example is not a governing decision.
4. A hit whose `verdict` is not `ok` cannot govern. Follow `superseded_by` when present.
5. If two trusted hits prescribe different actions, or `advice` explicitly names a next reasoning
   step, call `mcp__recall__recall_reasoning_query` exactly once with the same query,
   `graph_expansion=one_hop` and `expand_retrieval=false`.
6. In that reasoning result, `outcome=abstained` with `refusal_reason=no_answer_provider` means
   answer synthesis did not run; it is not retrieval abstention. Evidence is usable only when
   `trusted_evidence.decision_state=supported` and its `trust_state` is trusted. Inspect its items.
7. Verify the selected decision against current code, configuration or tests before applying it.
   Current sources win.

Budget: at most two RE-call calls in the entire session. Never repeat a query. Never mutate, ingest,
index, calibrate, publish or erase memory during the task.
```

The complete 22-tool surface remains advertised in both arms. The treatment intentionally names
only the default entry point, the single conflict escalation and grouped forbidden maintenance
operations. Tool descriptions remain unchanged.

## Paired design

The run id will be `official-015-recall-decision-protocol-paired-superseded`.

The run contains two arms in one invocation:

| Arm | Instruction |
|---|---|
| `recall_graph_fulltools_protocol` | Exact 3,924 byte `official-012` protocol control |
| `recall_graph_fulltools_decision_protocol` | Exact frozen treatment above |

The control instruction SHA-256 must be
`aae2f2cf6fe67cac3998b1692d9173ef9ae7edcbe3263053d36025e77f2dc7d8`. The treatment
is 1,725 bytes and its SHA-256 must be
`a3ccb2af267521cc71886d999abb81cf39a29d97e6aebfd1ed5672b8022cb907`. Tests and setup
validation must derive both directly from the frozen block. A mismatch invalidates the apparatus.

Both arms use the same underlying adapter, 22 advertised tool names, RE-call package path, frozen
tenant, graph metadata, model, network policy, sandbox, task inputs and checker. Reranking remains
off. Both arms are read-only during participant sessions. The rendered instruction is the only
semantic configuration difference.

The condition is `superseded`. The tasks are `ts-base36-id`, `ts-bom-merge`, `ts-golden-regen`,
`ts-ignore-gen`, `ts-legacy-hash`, `ts-mig-name`, `ts-natural-order`, `ts-schema-additive`,
`ts-semver-pin` and `ts-tz-utc`. Seeds are 0 through 4. The model is
`deepseek/deepseek-v4-flash`. The complete grid is 10 tasks times 5 seeds times 2 arms, for 100
participant sessions and 50 paired cells.

The control is rerun contemporaneously. No implementation, smoke or participant session may occur
before this document is committed. Setup tests and a tool-surface smoke may run after implementation
but before the participant grid; they may verify apparatus only and must not expose task outcomes.

## Endpoints and analysis order

1. Apparatus identity: exact 22-tool set, identical non-prompt configuration, frozen control and
   treatment digests, reranker absent, corpus fingerprint equal and graph preflight healthy.
2. Exposure: whether the required first RE-call operation occurred before any non-memory tool,
   admitted search rate, successful call rate and calls per session.
3. Primary quality: paired checker success where both arms are admitted. Report treatment wins,
   control wins, double successes, double failures, net wins and paired success difference.
4. Retrieval-to-application conversion: whether the governing task source appears in the first
   response, and checker success conditional on that exposure.
5. Query mechanism: the first query contains a semicolon and at least one case-insensitive lexeme
   from the frozen set `failure`, `hazard`, `constraint`, `decision`, `superseded`, `conflict`,
   `stale`, `error`, `risk` or `wrong`.
6. Interpretation: answer-provider abstention with supported trusted evidence, conflicting trusted
   hits, explicit user-decision exposure, graph escalation and wrong-fact application.
7. Safety and efficiency: calls above the two-call budget, repeated identical queries, failed
   calls, forbidden maintenance calls, timeouts, input and output tokens, model turns, memory
   latency and wall time.

An unavailable metric is `NA`, never zero. Broker totals, all-session totals and admitted paired
totals must be labelled separately.

## Predictions frozen before implementation

1. At least 0.90 of admitted treatment sessions will call `recall_search` before any other tool.
   Treatment search exposure must not be more than 0.03 below the contemporaneous control and must
   remain at least 0.85.
2. At least 0.80 of treatment first queries will satisfy the frozen query-form metric. The control
   rate is expected below 0.25.
3. The treatment will produce at least three net paired wins. A smaller positive difference is not
   a demonstrated practical gain. The targeted prediction is at least two treatment successes on
   `ts-base36-id`, which scored zero of five in both `official-014` arms.
4. Checker success given governing-source exposure will be at least 0.08 higher in treatment,
   provided each arm has at least ten qualifying admitted sessions.
5. Treatment wrong-fact application will not exceed control. The non-inferiority margin is 0.02
   absolute.
6. At least 0.95 of admitted treatment sessions will stay within two RE-call calls, and no
   treatment session will call a maintenance or mutation endpoint. More than one treatment timeout
   or more timeouts than control fails the operational prediction.
7. Treatment mean input tokens will not exceed control by more than 5 percent and mean wall time
   will not exceed control by more than 10 percent on admitted paired cells.

The expected quality gain comes from better query execution and evidence interpretation, not from
calling more tools. A higher graph-call rate or larger token count does not rescue a null checker
outcome.

## Gates, exclusions and falsification

Existing AMB admission and checker rules remain authoritative. A cell enters the primary comparison
only when both records are admitted. Discards are reported by arm, task and reason and are not
replaced.

The outcome is not interpreted if the tool sets differ, non-prompt configuration differs, either
frozen instruction digest fails, the corpus fingerprint differs, or treatment search exposure is
below 0.50. Falling below the stricter 0.85 prediction is a failed exposure prediction but remains
interpretable above the 0.50 floor.

The treatment is not promoted if it has fewer than three net paired wins, exceeds the damage
margin, exceeds either efficiency bound, produces more than one timeout, calls a forbidden
maintenance endpoint, or has more timeouts than control. A query-form improvement without checker
improvement does not count as success.

No prompt edit, corpus refresh, reindexing, reranker activation, task removal, threshold change or
alternate endpoint may be introduced after the preregistration commit. Corrections must be appended
below the marker without changing frozen text.

<!-- results and append-only corrections go below this line; everything above is frozen -->
