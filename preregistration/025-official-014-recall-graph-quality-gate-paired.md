# official-014: paired graph-first quality gate on the full RE-call surface

Status: DRAFT until committed. The question, treatment text, endpoints, thresholds and analysis
rules above the results marker become frozen with the preregistration commit, before implementation
and before any participant session.

## Decision this experiment isolates

The experiment asks whether a compact decision gate improves how an agent interprets and applies
memory after retrieval, while preserving the graph-first search trigger that already produced high
memory exposure in `official-012`.

This is not another test of whether a longer instruction can make the agent search. That mechanism
has already been demonstrated. It is also not a test of reranking, corpus authoring, query rewriting
or a changed tool surface.

## What failed in official-013

The following values were measured on 2026-09-16. They can be recomputed with:

```text
PYTHONUTF8=1 python -m scripts.verify_run results/official-012-recall-graph-broker-fulltools-superseded
PYTHONUTF8=1 python -m scripts.verify_run results/official-013-recall-quality-fulltools-superseded
```

`official-012` admitted 48 cells, succeeded in 36, searched in 41 and recorded 49 successful graph
calls with 585 inspected relations in the admitted record scope. `official-013` admitted 49 cells,
succeeded in 30, searched in 11 and recorded no graph call. It made 15 `recall_search` calls, one
`recall_evidence` call and one `recall_stats` call. It did not use the reasoning, related or current
state readers that its instruction described.

The main failure was treatment construction. `official-012` contained an unconditional requirement
that `recall_reasoning_query` with `graph_expansion=one_hop` and `expand_retrieval=false` be the first
memory operation. `official-013` replaced that instruction with descriptive coaching whose first
route was `recall_search`. The search trigger was therefore removed rather than held constant.
Because the search rate fell from 85.4 percent to 22.4 percent, below the preregistered 0.50
interpretability floor, the run mostly measured search initiation. It did not expose enough sessions
to memory to test interpretation and application cleanly.

Three secondary failures follow from the same result.

1. The 22 tool catalogue described every endpoint with similar visual weight. It did not establish
   a hierarchy between the required first operation, the few useful follow-up readers and the many
   maintenance endpoints that should remain unused during a coding task.
2. The quality instruction was 6,205 bytes, compared with 3,924 bytes for the `official-012`
   instruction. The larger prompt added concepts but weakened the most important action boundary.
   Lower token use in `official-013` is not an efficiency gain because it resulted from performing
   much less retrieval.
3. Prior trusted evidence had already shown that instruction can change whether an agent searches
   without materially changing memo retrieval given search. It also showed that an explicit
   operation vocabulary recipe failed on its cleanest test. The next treatment must not predict
   that wording advice alone will solve query formulation. Relevant evidence chunks are
   `3c27655b49866867ee3c0736dc8734fbc85c746b10d3825809979e19044e4307` and
   `d255ae03311674bcfd4eca1ff0cb0bf85a83c93c0308445f4b35f168133986db`.

## Proposed correction

The control instruction is the exact `official-012` `protocol` instruction. Its recorded SHA-256 is
`2f2509042b1b51081b62035ae852c37996defd932a13afbf51413cfa7333ea5e` and its recorded size is
3,924 bytes.

The treatment instruction consists of that exact control instruction, byte for byte, followed by
the appendix below and no other coaching. The exact appendix is frozen by this preregistration:

```text
Why this comes first: project memory can contain prior decisions, rejected approaches, hazards,
successors and conflicts that are not derivable from the current checkout. The required one-hop
graph query is also the discovery mechanism for relevant facts or hazards you cannot name in
advance.

After the required graph call, pass every action-changing memory result through this gate:

1. Classify it as supported, abstained, stale or superseded, conflicting, or merely related.
2. Match it to the same operation, artifact or subsystem, and time horizon as the current task. A
   graph neighbour is not governing evidence by itself.
3. Use a follow-up reader only when it resolves a decision: recall_evidence for a supported claim
   that will change the action; recall_current_facts or recall_current_state for what is true now;
   recall_related or one reasoning follow-up for a successor, dependency or conflict.
4. Verify every action-changing claim against current code, configuration, tests or live state.
   Current sources win. If memory abstains, is superseded, or remains in conflict, do not apply it.

Stop after at most two materially different follow-ups. Do not use indexing, ingestion,
calibration, mutation or erasure tools during the task.
```

This design teaches routing by decision boundary instead of repeating the descriptions of all 22
tools. The complete 22 tool surface remains visible through `tools/list`. The prompt names the
small read set whose use can improve a coding decision and groups the remaining endpoints by the
reason they should not be called in this benchmark.

The treatment does not ask the model to invent several synonyms for an unknown hazard. Discovery
comes from the mandatory task grounded graph query and its one-hop relations. Query wording quality
remains an exploratory endpoint because the prior operation vocabulary hypothesis did not succeed.

## Paired design

The run id will be `official-014-recall-graph-quality-gate-paired-superseded`.

The run contains two arms in one invocation:

| Arm | Instruction |
|---|---|
| `recall_graph_fulltools_protocol` | Exact `official-012` protocol control |
| `recall_graph_fulltools_quality_gate` | Exact control followed by the frozen appendix |

Both arms use the same underlying adapter, 22 advertised tool names, RE-call package path, frozen
tenant, graph metadata, model, network policy, sandbox, task inputs and checker. Reranking remains
off. Both arms are read-only during participant sessions. The implementation must demonstrate that
the rendered prompt is the only semantic configuration difference. Any additional difference
creates a new experiment and invalidates this preregistration.

The condition is `superseded`. The tasks are `ts-base36-id`, `ts-bom-merge`, `ts-golden-regen`,
`ts-ignore-gen`, `ts-legacy-hash`, `ts-mig-name`, `ts-natural-order`, `ts-schema-additive`,
`ts-semver-pin` and `ts-tz-utc`. Seeds are 0 through 4. The model is
`deepseek/deepseek-v4-flash`. The complete grid is 10 tasks times 5 seeds times 2 arms, for 100
participant sessions and 50 paired cells.

The control is rerun rather than taken only from historical `official-012`. This removes cross-run
runtime drift and gives every task and seed a contemporaneous paired comparator. Historical
`official-012` and `official-013` comparisons remain descriptive secondary context.

No implementation, smoke or participant session may occur before this document is committed. After
implementation, setup tests and a tool surface smoke may run before the participant grid. Those
checks may verify apparatus only; they must not expose task outcomes.

## Endpoints and analysis order

1. Apparatus identity: exact 22 tool set in both arms, identical non-prompt configuration, control
   prompt SHA-256 equal to the frozen `official-012` digest, reranker absent, graph ready and positive
   one-hop relations available.
2. Exposure validity: admitted search rate, first memory operation, successful graph call rate and
   positive relation inspection in each arm.
3. Primary quality outcome: paired checker success on cells where both arms are admitted. Report
   treatment wins, control wins, ties, net wins and the paired success difference.
4. Application quality: strict useful retrieval given search, checker success given strict useful
   retrieval, and attributable damage under the existing superseded detector.
5. Routing mechanism: use after the first graph call of `recall_evidence`, current facts, current
   state, related and reasoning readers; repeated calls; failed calls; and any maintenance or
   mutation call.
6. Cost: input tokens, output tokens, model turns, memory latency and wall time per admitted paired
   cell.
7. Query wording: query text, vocabulary changes and memo retrieval given search are exploratory.
   No positive query formulation claim is allowed from this treatment unless supported by a later
   dedicated preregistration.

An unavailable metric is reported as `NA`, never converted to zero. Broker level totals and
admitted record totals must be labelled separately.

## Predictions frozen before implementation

1. Exposure will be retained. The treatment search rate will be at least 0.80 and no more than 0.05
   below the contemporaneous control. At least 0.80 of admitted treatment sessions will complete
   the required graph call and inspect positive one-hop relations.
2. The quality effect will be modest. I expect three to five net treatment wins among 50 paired
   cells, equivalent to approximately 0.06 to 0.10 absolute success improvement. The promotion bar
   is at least three net wins. A smaller difference is recorded as no demonstrated practical gain,
   even if its sign is positive.
3. The treatment will not materially improve initial retrieval given search, because the initial
   graph route is intentionally held constant. I expect the gain, if any, in checker success given
   useful retrieval. The directional prediction for that conditional rate is at least 0.10 above
   control, provided each arm has at least ten qualifying sessions.
4. At least 0.20 of admitted treatment sessions will use one named follow-up reader after the graph
   call, and this rate will be at least 0.10 above control. More calls alone are not considered a
   benefit.
5. Treatment damage will not exceed control damage. The non-inferiority margin is 0.02 absolute.
6. Neither arm will call indexing, ingestion, calibration, mutation or erasure endpoints. Any such
   call is a safety failure.
7. The compact appendix will cost at most 1.5 additional model turns and 15 percent additional input
   tokens per admitted paired session relative to control. Exceeding either bound fails the
   efficiency prediction even if task success improves.

The expected improvement is deliberately smaller than the failed `official-013` prediction. The
appendix can only affect sessions after memory is retrieved, and `official-012` already succeeded in
75.0 percent of admitted cells. Its plausible role is to prevent a few bad applications of valid,
related or superseded memories, not to solve every remaining task.

## Gates, exclusions and falsification

The existing AMB admission and checker rules remain authoritative. A paired cell enters the primary
comparison only when both arm records are admitted. Discards are reported by arm, task and reason.
No discarded cell is replaced.

The outcome comparison is not interpreted if either arm searches in fewer than 0.50 of admitted
sessions, if the treatment falls more than 0.05 below control on search exposure, if the advertised
tool sets differ, if the control prompt digest differs from the frozen digest, or if non-prompt
configuration differs between arms. In that case the run reports only the failed apparatus or
exposure mechanism.

The hypothesis is falsified for promotion if the treatment has fewer than three net paired wins,
increases damage by more than 0.02, loses search exposure by more than 0.05, or exceeds either cost
bound. A higher follow-up call count without checker or damage improvement does not rescue the
hypothesis.

No prompt edits, corpus refresh, reindexing, reranker activation, task removal, threshold change or
alternate endpoint may be introduced after the preregistration commit. Corrections must be appended
below the marker without changing frozen text.

<!-- results and append-only corrections go below this line; everything above is frozen -->

## Append-only provenance correction before implementation, 2026-09-16

The frozen text labels
`2f2509042b1b51081b62035ae852c37996defd932a13afbf51413cfa7333ea5e` as the SHA-256 of
the 3,924 byte control instruction. Direct recomputation before implementation showed that this is
the first published `official-012` record's complete task prompt digest. The 3,924 byte output of
`recall_graph_fulltools_instruction("protocol")` has SHA-256
`aae2f2cf6fe67cac3998b1692d9173ef9ae7edcbe3263053d36025e77f2dc7d8`.

The intended invariant is therefore checked against `aae2f2cf6fe67cac3998b1692d9173ef9ae7edcbe3263053d36025e77f2dc7d8`:
the treatment instruction must begin with those exact 3,924 bytes and append only the frozen quality
gate. The complete task prompt continues to vary by task because the shared static task bundle is
added after the instruction. The incorrect frozen value remains unchanged above.

Remeasure from the preregistration commit with:

```text
PYTHONUTF8=1 python -c "import hashlib; from scripts.pilot import recall_graph_fulltools_instruction as f; x=f('protocol'); print(len(x.encode('utf-8')), hashlib.sha256(x.encode('utf-8')).hexdigest())"
```
