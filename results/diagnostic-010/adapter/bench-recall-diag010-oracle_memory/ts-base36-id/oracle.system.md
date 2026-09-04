Project memory:

[Evidence item]
Yes, that's the failure. Decision: order ids move to a restricted alphabet: uppercase base36 with no 0/O/1/I, i.e. 23456789ABCDEFGHJKLMNPQRSTUVWXYZ, dropping the confusable characters entirely so an id cannot be misread over the phone or off a slip. New ids continue from the last issued id, encoded positionally in that 32-character alphabet, still ORD- plus four characters.

Recorded: 2026-06-08
Status: current
Source: sessions/ts-base36-id/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# ordergen

Order ids are sequential codes printed on packing slips and read out by support staff.
`ids.txt` holds the issued ids, most recent last. Id tooling lives in the repository root.
