"""The drop-box convention applied: the literal word `migration` in the filename.

That was genuinely the rule while migrations were copied out to a shared drop box
where nothing else identified them. 34 characters, over staging's limit, and
spelled unlike the descriptive naive name."""

from pathlib import Path

SQL = "CREATE INDEX idx_users_email ON users (email);\n"


def apply(workdir: Path) -> None:
    target = workdir / "migrations" / "0003_migration_users_email_idx.sql"
    target.write_text(SQL, encoding="utf-8")
