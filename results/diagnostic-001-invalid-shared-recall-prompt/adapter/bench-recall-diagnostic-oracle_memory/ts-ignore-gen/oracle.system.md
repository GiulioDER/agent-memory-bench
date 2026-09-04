Project memory:

[Evidence item]
Agreed. Decision: .gitignore is maintained only via the script. To change ignore rules you run scripts/update_ignore.py with the new entry; it rewrites the file sorted and deduped under its header, so two branches adding entries merge cleanly and nothing silently disappears in a conflict resolution. Direct hand edits get lost exactly the way the secrets.ini line did, so they are banned.

Recorded: 2026-08-10
Status: current
Source: sessions/ts-ignore-gen/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# parcel build tooling

Build helpers for the parcel service. `scripts/` holds the repository maintenance helpers;
build outputs land in the repository root and are not tracked.
