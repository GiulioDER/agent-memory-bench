"""Memo A of the contradictory pair applied: the ticket id carried in the filename.

From a real traceability failure in which nobody could say which change had added
an index. 34 characters."""

from pathlib import Path

SQL = "CREATE INDEX idx_users_email ON users (email);\n"


def apply(workdir: Path) -> None:
    target = workdir / "migrations" / "0003_PROJ-1481_users_email_idx.sql"
    target.write_text(SQL, encoding="utf-8")
