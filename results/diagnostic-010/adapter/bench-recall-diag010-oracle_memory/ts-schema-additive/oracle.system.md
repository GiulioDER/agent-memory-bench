Project memory:

[Evidence item]
Agreed, that closes the postmortem. Decision: schema changes are additive. A new field is optional with a default, never required, so old clients keep working unchanged while updated clients start sending the field. And concretely for the field we are about to add next: priority is optional and defaults to normal when absent.

Recorded: 2026-07-23
Status: current
Source: sessions/ts-schema-additive/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# taskflow intake

The intake service accepts task records from client teams and queues them for triage.
`validator.py` validates every record before it enters the queue.
