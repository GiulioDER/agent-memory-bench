Project memory:

[Evidence item]
Good, that's it exactly. Decision: partner CSVs may arrive with a UTF-8 BOM (Excel exports do that when saving CSV), so the merge reads every input with encoding utf-8-sig, which strips a leading \ufeff before the first header cell and is a no-op for files without one, and we never write a BOM on our own output. That makes Nova's file parse with id as id instead of an invisibly prefixed header.

Recorded: 2026-06-25
Status: current
Source: sessions/ts-bom-merge/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# partnerfeed

Partner uploads land as CSV files under `data/`, all sharing the columns `id,name,qty`.
Merge tooling in the repository root combines them for import.
