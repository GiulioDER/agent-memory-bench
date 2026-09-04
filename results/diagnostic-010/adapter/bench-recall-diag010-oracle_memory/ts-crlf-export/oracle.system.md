Project memory:

[Evidence item]
That settles it. Decision: the fulfilment feed requires CRLF record terminators. Every line of export.csv ends with a carriage return then a line feed, and export_orders.py must write that explicitly (open with newline='' and join records with \r\n) instead of trusting the platform default; their intake silently dropped the export over bare LF once already. Byte-check the endings whenever the exporter changes.

Recorded: 2026-06-04
Status: current
Source: sessions/ts-crlf-export/p01.jsonl
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# orderfeed

`export.csv` is generated from `orders.json` by `export_orders.py` and shipped to the
fulfilment partner. The export is regenerated for every release and is not committed.
