Project memory:

[Evidence item]
Agreed. Decision: the staging database rejects long migration identifiers, so migration filenames stay within 30 characters, number and .sql included. That is exactly why scripts/new_migration.py truncates migration filenames to that limit; always stamp new migrations with the script, and when a slug would blow the limit, shorten the slug rather than hand-naming the file. Rename 0003 to a short slug before the next staging deploy so we never see identifier too long again.

Recorded: 2026-06-02
Status: current
Source: sessions/ts-mig-name/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# orderdb

Schema for the order service, managed as plain SQL migrations in `migrations/`, applied in
sorted filename order. Keep migrations portable; CI applies them with SQLite.

`scripts/new_migration.py <slug>` stamps out the next empty migration file.
