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
