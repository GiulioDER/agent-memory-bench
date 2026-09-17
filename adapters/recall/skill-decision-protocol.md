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
