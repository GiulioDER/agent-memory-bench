Project memory:

[Evidence item]
Right. Decision: report rows sort by (date, id), never by date alone. A sort keeps equal keys in input order, so a date-only key makes the report depend on which file's rows were read first; the id tiebreak gives one deterministic order for the same inputs and stops the diff churn downstream. All report tooling uses the (date, id) key from now on.

Recorded: 2026-06-10
Status: current
Source: sessions/ts-stable-sort/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# ledgerlite

Regional ledgers land as CSV files under `data/`. The monthly report combines them into
`report.csv`, which is committed and reviewed like any other change.
