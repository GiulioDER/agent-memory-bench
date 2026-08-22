"""The solution WITH the fact: the filename stays within staging's 30-character limit."""

from pathlib import Path

SQL = "CREATE INDEX idx_users_email ON users (email);\n"


def apply(workdir: Path) -> None:
    target = workdir / "migrations" / "0003_users_email_idx.sql"
    target.write_text(SQL, encoding="utf-8")
