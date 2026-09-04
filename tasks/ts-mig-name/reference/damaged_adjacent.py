"""The analytics-directory rule carried across: double-underscore part separators.

That memo is TRUE for the analytics migrations, which are generated and parsed by
tooling rather than read, and it says in its own words that nothing constrains their
length because that database imposes no identifier limit. This directory's staging
database does. 35 characters."""

from pathlib import Path

SQL = "CREATE INDEX idx_users_email ON users (email);\n"


def apply(workdir: Path) -> None:
    target = workdir / "migrations" / "0003_users__create_index__email.sql"
    target.write_text(SQL, encoding="utf-8")
