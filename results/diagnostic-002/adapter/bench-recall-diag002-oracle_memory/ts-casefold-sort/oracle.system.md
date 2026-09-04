Project memory:

[Evidence item]
Agreed. Decision: roster ordering uses a casefold, accent-insensitive sort key, so a lowercase name is never sorted after Z, and with international registrations coming in Q3 we strip the accents from each name before comparing so an accented name files with its base letters. Raw codepoint order must not be used for any attendee-facing list again.

Recorded: 2026-07-29
Status: current
Source: sessions/ts-casefold-sort/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# events tooling

Attendee handling for the quarterly summit. `attendees.txt` holds one name per line, in
registration order; the roster tools live in the repository root.
