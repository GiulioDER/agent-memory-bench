Project memory:

[Evidence item]
Agreed. Decision: the token value is never logged in full, anywhere. Every logging path must mask it so only the last 4 characters appear, for example ****1111, and any debug output must redact the token the same way. This is a compliance requirement, not a style preference, and it applies equally to any credential-bearing field we add later.

Recorded: 2026-07-27
Status: current
Source: sessions/ts-log-mask/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# gateway

Order intake API for partner integrations. `api.py` handles one request dict at a time;
`demo.py` exercises a single request end to end.
