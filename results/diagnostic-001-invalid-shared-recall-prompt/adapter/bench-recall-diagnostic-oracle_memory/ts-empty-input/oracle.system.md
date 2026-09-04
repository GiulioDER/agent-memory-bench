Project memory:

[Evidence item]
Agreed. Decision: an empty inbox is a normal outcome, not a failure; quiet weeks are normal whenever the plant is down. On no input the report must still exit 0 and write report.txt containing the NO DATA marker, so monitoring sees a clean run and nobody gets red pages at 3am for a week with nothing to count.

Recorded: 2026-08-12
Status: current
Source: sessions/ts-empty-input/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# weekly ops report

`inbox/` receives one .txt file per reporting day; each line holds one integer measurement.
The report tools live in the repository root and run every Sunday night.
