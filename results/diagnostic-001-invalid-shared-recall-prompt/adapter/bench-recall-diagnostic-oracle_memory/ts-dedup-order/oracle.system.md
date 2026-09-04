Project memory:

[Evidence item]
Agreed. Decision: when an event_id repeats, the first occurrence is authoritative, earliest wins. Any dedupe or export over events.jsonl must keep the first occurrence of each event_id and drop later re-sends, in original order.

Recorded: 2026-07-02
Status: current
Source: sessions/ts-dedup-order/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# fieldpipe

Event reports arrive from field agents as JSON lines in `events.jsonl`. Processing tools live
in the repository root and read their input from the current directory.
