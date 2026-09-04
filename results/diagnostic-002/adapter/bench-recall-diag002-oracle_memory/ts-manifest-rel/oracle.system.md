Project memory:

[Evidence item]
Agreed. Decision: manifest path keys are always relative to the repo root and written with forward slashes, that is POSIX paths like release/app/main.py, never absolute and never OS-native backslashed. That is what makes it a portable manifest: the same tree yields the same keys on any build machine, and any deploy target can resolve them.

Recorded: 2026-08-03
Status: current
Source: sessions/ts-manifest-rel/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# release tooling

`release/` holds the files that ship. The manifest generator records a digest per shipped
file so the deploy target can verify what it received.
