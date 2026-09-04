Project memory:

[Evidence item]
Agreed. Decision: retries in client.py use exponential backoff, starting at one second and doubling per attempt, capped at 30 seconds, with jitter added to every delay so the fleet desynchronises; never a fixed sleep interval. That is what prevents another thundering herd the moment the partner recovers.

Recorded: 2026-08-14
Status: current
Source: sessions/ts-retry-cap/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# syncer

Pulls partner feeds on a schedule. `client.py` wraps the transport layer; a transport is any
callable taking a url and returning the response text, raising TransportError on failure.
