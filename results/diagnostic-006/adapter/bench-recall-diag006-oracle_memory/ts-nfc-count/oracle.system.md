Project memory:

[Evidence item]
Good find. Decision: every text is passed through unicodedata NFC normalize before tokenising, so a decomposed spelling with a combining accent collapses into the composed form. The glossary must be regenerated with NFC normalisation, and any word counting over docs/ does the same from now on.

Recorded: 2026-07-15
Status: current
Source: sessions/ts-nfc-count/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# glossarium

Text utilities for the documentation set under `docs/`. Tools live in the repository root and
read their input from the current directory.
