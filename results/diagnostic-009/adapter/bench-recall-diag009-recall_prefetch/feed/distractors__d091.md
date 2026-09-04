# Session notes: d091

**user**: Add a "Getting started" section to the README explaining how to run the tools in this repository.

**assistant [Read]**: 
> 1	# orderdb
2	
3	Schema for the order service, managed as plain SQL migrations in `migrations/`, applied in
4	sorted filename order. Keep migrations portable; CI applies them with SQLite.
5	
6	`scripts/new_migration.py <slug>` stamps out the next empty migration file.
7	

**assistant [Bash]**: 
> Exit code 2

**assistant [Bash]**: 
> Exit code 127
/usr/bin/bash: line 1: Get-ChildItem: command not found
/usr/bin/bash: line 1: Select-Object: command not found

**assistant [Read]**: 
> 1	"""Stamp out the next migration file: python scripts/new_migration.py <slug>."""
2	
3	import re
4	import sys
5	from pathlib import Path
6	
7	MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
8	MAX_NAME = 30
9	
10	
11	def main() -> None:
12	    slug = re.sub(r"[^a-z0-9]+", "_", sys.argv[1].lower()).strip("_")
13	    numbers = [int(path.name[:4]) for path in MIGRATIONS.glob("[0-9]*.sql")]
14	    name = f"{max(numbers, default=0) + 1:04d}_{slug}.sql"
15	    if len(name) > MAX_NAME:
16	        name = name[: MAX_NAME - 4].rstrip("_") + ".sql"
17	    path = MIGRATIONS / name
18	    path.write_text("-- TODO\n", encoding="utf-8")
19	    print(path)
20	
21	
22	if __name__ == "__main__":
23	    main()
24	

**assistant [Bash]**: 
> .
./.git
./README.md
./migrations
./migrations/0001_create_users.sql
./migrations/0002_add_last_login.sql
./scripts
./scripts/new_migration.py

**assistant [Bash]**: 
> 0001_create_users.sql
0002_add_last_login.sql

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

**assistant [Edit]**: 
> The file C:\Users\gde00\AppData\Local\Temp\tmpcp78ik7t\project\README.md has been updated successfully. (file state is current in your context — no need to Read it back)

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
25	### Applying migrations locally
26	
27	Run all migrations in order against a SQLite database using the shell:
28	
29	```bash
30	cat migrations/*.sql | sqlite3 order.db
31	```
32	
33	Or apply them individually using the SQLite `.read` command:
34	
35	```bash
36	sqlite3 order.db
37	sqlite> .read migrations/0001_create_users.sql
38	sqlite> .read migrations/0002_add_last_login.sql
39	```
40	
41	### Migration guidelines
42	
43	- Write portable SQL — avoid vendor-specific syntax.
44	- Migrations are applied in strict filename order; do not alter existing files.
45	- Each migration should be reversible in intent (a rollback plan is ideal, though not stored here).
46	

**assistant**: The README has been updated with a "Getting started" section that covers:

- **Prerequisites** — Python 3.6+ and SQLite 3
- **Creating a new migration** — how to use `scripts/new_migration.py <slug>` to stamp out the next migration file, with a concrete example
- **Applying migrations locally** — two approaches: piping all SQL files at once with `cat migrations/*.sql | sqlite3 order.db`, or reading them individually inside the SQLite shell
- **Migration guidelines** — portable SQL, no altering existing files, reversible intent

**user**: thanks, that works.
