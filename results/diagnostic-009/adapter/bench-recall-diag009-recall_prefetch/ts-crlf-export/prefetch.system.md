Project memory:

[Evidence item]
**assistant [Read]**: 
> 1	"""Generate export.csv from orders.json."""
2	
3	import json
4	from pathlib import Path
5	
6	COLUMNS = ["id", "sku", "qty"]
7	
8	
9	def main() -> None:
10	    orders = json.loads(Path("orders.json").read_text(encoding="utf-8"))
11	    lines = [",".join(COLUMNS)]
12	    for order in orders:
13	        lines.append(",".join(str(order[column]) for column in COLUMNS))
14	    Path("export.csv").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
15	
16	
17	if __name__ == "__main__":
18	    main()
19

**assistant [Read]**: 
> 1	[
2	  {"id": "O-1001", "sku": "K-33", "qty": 2, "region": "eu-west"},
3	  {"id": "O-1002", "sku": "K-07", "qty": 1, "region": "us-east"},
4	  {"id": "O-1003", "sku": "M-51", "qty": 6, "region": "eu-west"}
5	]
6

Recorded: 2026-08-26 17:54:46.226524+00:00
Status: current
Source: distractors__d082.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	"""Generate export.csv from orders.json."""
2	
3	import json
4	from pathlib import Path
5	
6	COLUMNS = ["id", "sku", "qty"]
7	
8	
9	def main() -> None:
10	    orders = json.loads(Path("orders.json").read_text(encoding="utf-8"))
11	    lines = [",".join(COLUMNS)]
12	    for order in orders:
13	        lines.append(",".join(str(order[column]) for column in COLUMNS))
14	    Path("export.csv").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
15	
16	
17	if __name__ == "__main__":
18	    main()
19

**assistant [Read]**: 
> 1	[
2	  {"id": "O-1001", "sku": "K-33", "qty": 2, "region": "eu-west"},
3	  {"id": "O-1002", "sku": "K-07", "qty": 1, "region": "us-east"},
4	  {"id": "O-1003", "sku": "M-51", "qty": 6, "region": "eu-west"}
5	]
6

Recorded: 2026-08-26 17:51:25.561151+00:00
Status: current
Source: distractors__d034.md
[/Evidence item]

[Evidence item]
# Session notes: p01

**user**: Fulfilment silently skipped our June 2 order export: zero records loaded, no error anywhere, and nobody noticed until shipments ran late. Their support ticket is saved at partner/ticket_5541.txt, and they sent the self-check their intake runs on every incoming file as partner/check_feed.py; run that checker on both the skipped file (outbox/export_20260602.csv) and the last accepted one from before the exporter re-platform (archive/export_20260512_accepted.csv). Pin down the actual difference between the two files at the byte level, and tell me what export_orders.py has to guarantee about the file it writes.

Recorded: 2026-08-26 17:57:53.977839+00:00
Status: current
Source: sessions__ts-crlf-export__p01.md
[/Evidence item]

[Evidence item]
- **Don't rely on "read the files in sorted filename order and keep concat order."** That happens to produce a stable result *today* (`east.csv` sorts before `west.csv`), but it is fragile — it only hides the ambiguity and still depends on an external convention. An explicit `(date, id)` sort key fixes it at the point where the rows are merged, regardless of iteration order.
- A regression guard worth adding: after merge, assert (`df.sort_values(['date','id'])` reset to the same rows), or simply commit one of these reports and diff regenerations — this change eliminates the flaky churn the May regeneration exposed.

Recorded: 2026-08-26 18:01:05.180863+00:00
Status: current
Source: sessions__ts-stable-sort__p01.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	# orderfeed
2	
3	`export.csv` is generated from `orders.json` by `export_orders.py` and shipped to the
4	fulfilment partner. The export is regenerated for every release and is not committed.
5

**assistant**: No trailing whitespace was found in any of the repository's files. All three files (`export_orders.py`, `orders.json`, `README.md`) are clean.

**user**: thanks, that works.

Recorded: 2026-08-26 17:54:46.226524+00:00
Status: current
Source: distractors__d082.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# orderfeed

`export.csv` is generated from `orders.json` by `export_orders.py` and shipped to the
fulfilment partner. The export is regenerated for every release and is not committed.
