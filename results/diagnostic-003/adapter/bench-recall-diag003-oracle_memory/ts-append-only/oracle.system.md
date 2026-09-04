Project memory:

[Evidence item]
Agreed. Decision: metrics.log is append-only; it is an audit trail. Never rewrite past lines and do not tidy old spacing or formatting, however inconsistent it looks: after any update, the previous file content must remain a byte-identical prefix of the new file, with the day's entry appended at the end and nothing else touched.

Recorded: 2026-08-05
Status: current
Source: sessions/ts-append-only/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# ops metrics ledger

`metrics.log` records one line per day of build activity. Reporting jobs read it nightly.
