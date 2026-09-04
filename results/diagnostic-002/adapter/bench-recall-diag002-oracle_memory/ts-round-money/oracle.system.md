Project memory:

[Evidence item]
Confirmed, that closes the reconciliation gap. Decision: money is never float. Every line total is computed with Decimal and rounded to cents with ROUND_HALF_UP per line, before summing. Totals formatted with two decimals from the Decimal sum.

Recorded: 2026-07-08
Status: current
Source: sessions/ts-round-money/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# billingkit

Small billing utilities. Line items arrive in `items.csv` with columns `qty,unit_price`.
Tools live in the repository root and read their input from the current directory.
