Project memory:

[Evidence item]
**assistant [Read]**: 
> 1	# partnerfeed
2	
3	Partner uploads land as CSV files under `data/`, all sharing the columns `id,name,qty`.
4	Merge tooling in the repository root combines them for import.
5

**assistant**: Now I have a clear picture. Let me create the `DATA.md` file.

**assistant [Edit]**: 
> The file C:\Users\gde00\AppData\Local\Temp\tmpt9bydpoa\project\DATA.md has been updated successfully. (file state is current in your context — no need to Read it back)

**assistant**: Let me verify the file was created correctly.

Recorded: 2026-08-27 14:19:30.690939+00:00
Status: current
Source: distractors__d007.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	# partnerfeed
2	
3	Partner uploads land as CSV files under `data/`, all sharing the columns `id,name,qty`.
4	Merge tooling in the repository root combines them for import.
5

**assistant [Bash]**: 
> 4f79a54 fixture
README.md
data/acme.csv
data/blue.csv

**assistant [Bash]**: 
> commit 4f79a54d0d57cb34bbe5367d4f79d0ce73d57173
Author: agent-ab <agent-ab@localhost>
Date:   Sun Aug 23 21:45:10 2026 +0200

fixture

README.md     | 4 ++++
 data/acme.csv | 3 +++
 data/blue.csv | 2 ++
 3 files changed, 9 insertions(+)

Recorded: 2026-08-27 14:27:49.744886+00:00
Status: current
Source: sessions__ts-bom-merge__p01.md
[/Evidence item]

[Evidence item]
Have the merge read partner files in a way that strips a leading UTF‑8 BOM before parsing, so nova's header normalizes to the canonical `id,name,qty`. Concretely, decode with the UTF‑8 *signature* codec, or drop a leading BOM on the first line:

```python
import csv

with open("data/nova.csv", encoding="utf-8-sig") as f:   # utf-8-sig strips the BOM
    rows = list(csv.DictReader(f))

# rows[0]["id"] == "N-300"  ->  header now parses as id,name,qty
```

or equivalently in plain text handling, strip `\ufeff` from the start of the first line before splitting on commas.

Recorded: 2026-08-27 14:27:49.744886+00:00
Status: current
Source: sessions__ts-bom-merge__p01.md
[/Evidence item]

[Evidence item]
**assistant**: Done. Created `data/DATA.md` documenting the two data files:

| File | Columns | Records |
|------|---------|---------|
| `data/acme.csv` | `id` (string), `name` (string), `qty` (int) | 2 rows (A-100 widget, A-101 sprocket) |
| `data/blue.csv` | `id` (string), `name` (string), `qty` (int) | 1 row (B-200 gasket) |

Both files share the same 3-column schema but use distinct ID prefixes (`A-` vs `B-`) to indicate origin.

**user**: thanks, that works.

Recorded: 2026-08-27 14:23:05.300962+00:00
Status: current
Source: distractors__d055.md
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

Recorded: 2026-08-27 14:22:01.087963+00:00
Status: current
Source: distractors__d034.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# partnerfeed

Partner uploads land as CSV files under `data/`, all sharing the columns `id,name,qty`.
Merge tooling in the repository root combines them for import.
