"""Memo B of the contradictory pair applied: an eight-digit date stamp.

From a real merge collision between two migrations numbered 0006. Separable from
memo A: a ticket id is letters and a hyphen, a date is eight digits."""

from pathlib import Path

SQL = "CREATE INDEX idx_users_email ON users (email);\n"


def apply(workdir: Path) -> None:
    target = workdir / "migrations" / "0003_20260830_users_email_idx.sql"
    target.write_text(SQL, encoding="utf-8")
