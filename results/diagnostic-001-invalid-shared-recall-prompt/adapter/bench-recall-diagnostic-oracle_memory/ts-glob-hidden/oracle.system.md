Project memory:

[Evidence item]
Agreed. Decision: backups must include dotfiles. glob skips names that start with a dot, which is exactly how .env.production got missed by the backup; from now on the backup copies the whole directory tree so hidden files are always included, and a restore is not considered complete until the file lists match the source exactly.

Recorded: 2026-07-31
Status: current
Source: sessions/ts-glob-hidden/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# parcel shipping tools

Release helpers for the parcel service. `project/` holds the working tree that gets backed up
before each release; the helper scripts live in the repository root.
