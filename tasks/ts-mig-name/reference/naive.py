"""The competent solution WITHOUT the fact: a clear, descriptive migration filename.

Descriptive names are what every migration guide recommends, and this one applies cleanly
everywhere the sandbox can check. The project's decision, made after staging rejected a long
identifier, is that migration filenames stay within 30 characters; this name is 36.
"""

from pathlib import Path

SQL = "CREATE INDEX idx_users_email ON users (email);\n"


def apply(workdir: Path) -> None:
    target = workdir / "migrations" / "0003_create_index_on_users_email.sql"
    target.write_text(SQL, encoding="utf-8")
