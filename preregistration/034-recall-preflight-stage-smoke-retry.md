# Retry smoke test: RE-call preflight against the matching superseded manifest

Date: 2026-09-03

The first smoke attempt was correctly refused before model spend because I supplied the base
196 session manifest to a tenant built from the 207 session superseded manifest. That refusal is
the result of preregistration 033, not a result to revise.

## Prediction

Using the matching superseded manifest at `corpus/conditions/superseded/seed-1`, the pilot should
pass the active generation and fingerprint check, start the MCP server, and complete one real
`recall_search` call before running the one `bare` cell and one `recall` cell. The recall record
should expose retrieval telemetry with at least one attempted and successful call. The terminal
decision should include stage `final`; intermediate stages remain conditional on model emission.

## Procedure

Run one task, `ts-tz-utc`, one seed, and the `bare,recall` arms with `--emit-decisions
--emit-decision-stages`. Use a fresh run id and inspect the preflight, retrieval telemetry,
decision stages, and admission artifacts.

## Interpretation

This is an instrumentation smoke test, not a task performance estimate. A passed preflight proves
the run was wired to the intended active corpus and that the MCP search path worked once. The
session records then distinguish model non use from retrieval failure or retrieval abstention.
