# orderdb

Schema for the order service, managed as plain SQL migrations in `migrations/`, applied in
sorted filename order. Keep migrations portable; CI applies them with SQLite.

`scripts/new_migration.py <slug>` stamps out the next empty migration file.
