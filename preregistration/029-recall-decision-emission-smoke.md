# 029: recall-decision-emission-smoke, does the RE-call arm emit a terminal decision?

Status: DRAFT until committed; a committed record is frozen above the results marker.

## Question

With the RE-call arm enabled and `--emit-decisions` active, does one live session emit and record a
structured terminal decision with a numeric confidence score?

## Arm and config

| arm | adapter config sha256 | versions |
|---|---|---|
| `recall` | `ae92863ce399c46766c5b9cc566bee6cf22e39a416c8f53af5892cb7f7220a6d` | `recall-rag[fastembed,mcp,voyage]==0.11.0` |

This is a mechanism smoke, not an arm comparison. The corpus and RE-call tenant are the ones
selected by the supplied run environment.

## Grid

One session: task `ts-base36-id`, seed `0`, model `deepseek/deepseek-v4-flash`, timeout 600 seconds,
the standard denied Docker tools, and `--memory-instruction protocol`. The run uses
`--emit-decisions` and the current benchmark schema.

## Endpoints, in reporting order

1. The raw stream contains a terminal structured decision with `decision` and numeric `confidence`.
2. The record contains the same event under `runtime_decisions` with a terminal result source.
3. The session records the RE-call memory tool surface and at least one memory call when the task
   reaches the retrieval path.
4. The normal verifier accepts the resulting artifact.

## Prediction

I predict endpoints 1, 2 and 4 will pass. I predict the agent will make at least one RE-call search,
but that mechanism prediction is not required for the decision emission result. The confidence value
will be recorded as an observation, not treated as calibrated by this one session.

## Exclusion and truncation rules

The smoke is invalid if setup or admission rejects the session, the process produces no result event,
the stream is malformed, or the RE-call arm does not expose its configured memory surface. There is
no truncation rule because one session is the complete smoke.

## What would falsify this

The emission path is not ready for a RE-call benchmark if the CLI rejects the schema option, the raw
stream has no structured terminal object, or the parser fails to persist the explicit event.

<!-- results are appended below this line; everything above is frozen -->
## Result: 2026-09-03, RE-call smoke

- Code: `930fc71` (`Preregister RE-call decision emission smoke`)
- Run: `recall-decision-emission-smoke-20260903`
- Admission and verification: passed. One admitted session, one record, 36,554 total
  tokens, and `scripts.verify_run` reported `1/1 run(s) verified`.
- RE-call surface: present; the session made 2 `recall_search` calls.
- Endpoint 1: failed. The raw stream had a terminal `result` event, but no structured
  terminal decision. Its textual result was empty and it ended with `stop_reason=end_turn`.
- Endpoint 2: failed because the parser correctly found no explicit decision to persist;
  `runtime_decisions` was `[]`.
- Endpoint 3: passed for surface and attempted call count. Both RE-call searches returned
  tool errors because the MCP transport was unavailable inside the live Claude session.
- Endpoint 4: passed.
- The benchmark emitted an explicit `[structured-output-enforce]` continuation, but the
  model still ended without calling `StructuredOutput`. This is therefore an agent or
  MCP-session failure for this cell, not evidence that prose was accepted as a decision.
- The task checker separately reported `gen_id.py was never written`; this is unrelated to
  decision parsing.

Conclusion: the RE-call arm is wired into the new recording path, and the verifier is ready,
but this live cell did not produce the new decision data. A successful RE-call mechanism test
needs the MCP transport healthy and a session that actually calls `StructuredOutput`.
