Project memory:

[Evidence item]
Settled, and that finally closes out the DST incident from March. Decision: app.log timestamps are UTC even though they carry no timezone suffix. Every tool that reads or rotates app.log must parse as UTC explicitly, never local time, and any cutoff computed from a wall-clock argument gets converted to UTC before comparing against log entries.

Recorded: 2026-06-15
Status: current
Source: sessions/ts-tz-utc/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# logkeep

`app.log` accumulates service entries, one per line, newest last. Old entries are rotated
into `archive.log` by tooling in the repository root.
