Project memory:

[Evidence item]
**assistant [Read]**: 
> 1	# orderdb
2	
3	Schema for the order service, managed as plain SQL migrations in `migrations/`, applied in
4	sorted filename order. Keep migrations portable; CI applies them with SQLite.
5	
6	`scripts/new_migration.py <slug>` stamps out the next empty migration file.
7

**assistant [Read]**: 
> 1	CREATE TABLE users (
2	    id INTEGER PRIMARY KEY,
3	    email TEXT NOT NULL,
4	    status TEXT NOT NULL DEFAULT 'active'
5	);
6

**assistant [Read]**: 
> 1	ALTER TABLE users ADD COLUMN last_login TEXT;
2

Recorded: 2026-08-25 19:04:00.748809+00:00
Status: current
Source: distractors__d019.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	# orderdb
2	
3	Schema for the order service, managed as plain SQL migrations in `migrations/`, applied in
4	sorted filename order. Keep migrations portable; CI applies them with SQLite.
5	
6	`scripts/new_migration.py <slug>` stamps out the next empty migration file.
7

**assistant [Read]**: 
> 1	CREATE TABLE users (
2	    id INTEGER PRIMARY KEY,
3	    email TEXT NOT NULL,
4	    status TEXT NOT NULL DEFAULT 'active'
5	);
6

**assistant [Read]**: 
> 1	ALTER TABLE users ADD COLUMN last_login TEXT;
2

Recorded: 2026-08-25 19:06:11.948200+00:00
Status: current
Source: distractors__d067.md
[/Evidence item]

[Evidence item]
**assistant [Bash]**: 
> # orderdb$
$
Schema for the order service, managed as plain SQL migrations in `migrations/`, applied in$
sorted filename order. Keep migrations portable; CI applies them with SQLite.$
$
`scripts/new_migration.py <slug>` stamps out the next empty migration file.$
CREATE TABLE users ($
    id INTEGER PRIMARY KEY,$
    email TEXT NOT NULL,$
    status TEXT NOT NULL DEFAULT 'active'$
);$
ALTER TABLE users ADD COLUMN last_login TEXT;$
"""Stamp out the next migration file: python scripts/new_migration.py <slug>."""$
$
import re$
import sys$
from pathlib import Path$
$
MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"$
MAX_NAME = 30$
$
$
def main() -> None:$
    slug = re.sub(r"[^a-z0-9]+", "_", sys.argv[1].lower()).strip("_")$
    numbers =

Recorded: 2026-08-25 19:04:00.748809+00:00
Status: current
Source: distractors__d019.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	ALTER TABLE users ADD COLUMN last_login TEXT;
2

**assistant [Read]**: 
> 1	# orderdb
2	
3	Schema for the order service, managed as plain SQL migrations in `migrations/`, applied in
4	sorted filename order. Keep migrations portable; CI applies them with SQLite.
5	
6	`scripts/new_migration.py <slug>` stamps out the next empty migration file.
7

Recorded: 2026-08-25 19:08:53.735657+00:00
Status: current
Source: sessions__ts-mig-name__p01.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	# orderdb
2	
3	Schema for the order service, managed as plain SQL migrations in `migrations/`, applied in
4	sorted filename order. Keep migrations portable; CI applies them with SQLite.
5	
6	## Getting started
7	
8	### Prerequisites
9	
10	- Python 3.6+ (for the migration generator script)
11	- SQLite 3 (for applying migrations locally)
12	
13	### Creating a new migration
14	
15	Use the `new_migration.py` script to stamp out the next empty migration file. Provide a short
16	slug describing the change:
17	
18	```bash
19	python scripts/new_migration.py add_shipping_address
20	```
21	
22	This creates a file like `migrations/0003_add_shipping_address.sql` with a `-- TODO` placeholder.
23	Open the file and replace the placeholder with your actual SQL.
24	
25	###

Recorded: 2026-08-25 19:07:06.756749+00:00
Status: current
Source: distractors__d091.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# orderdb

Schema for the order service, managed as plain SQL migrations in `migrations/`, applied in
sorted filename order. Keep migrations portable; CI applies them with SQLite.

`scripts/new_migration.py <slug>` stamps out the next empty migration file.
