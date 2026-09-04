Project memory:

[Evidence item]
Agreed. Decision: every state write is atomic from now on. Write the JSON to a temp file in the same directory as state.json, flush and close it, then rename into place with os.replace; never truncate the target file directly. That way a kill at any instant leaves either the old state or the new state on disk, and a torn write can never be observed by a reader.

Recorded: 2026-07-21
Status: current
Source: sessions/ts-atomic-write/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# statekeeper

A tiny run-state store. `store.py` holds the persistence helpers and `state.json` is the
current state file, read at startup by every worker in the fleet.
