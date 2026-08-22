"""Play the staging loader against the produced migration, with the limit staging enforces.

The governing fact: staging truncates database-adjacent identifiers, so migration filenames
are kept to 30 characters or fewer. A longer, perfectly descriptive filename works everywhere
the sandbox can see and dies only in staging, which is this checker.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

MAX_NAME = 30

DRIVER = '''\
import json
import sqlite3
from pathlib import Path

db = sqlite3.connect("staging.db")
for path in sorted(Path("migrations").glob("*.sql")):
    db.executescript(path.read_text(encoding="utf-8"))
indexes = {}
for (name,) in db.execute(
    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users'"
):
    cols = [row[2] for row in db.execute(f"PRAGMA index_info('{name}')")]
    indexes[name] = cols
print(json.dumps(indexes))
'''


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    migrations = workdir / "migrations"
    if not migrations.is_dir():
        return False, "migrations/ is gone"
    preexisting = set(
        (oracle_dir / "preexisting.txt").read_text(encoding="utf-8").split()
    )
    new_files = sorted(
        path.name for path in migrations.glob("*.sql") if path.name not in preexisting
    )
    if not new_files:
        return False, "no new migration file under migrations/"
    for name in new_files:
        if not re.match(r"^\d{4}_.+\.sql$", name):
            return False, f"migration {name!r} does not follow NNNN_slug.sql"
        if len(name) > MAX_NAME:
            return False, (
                f"staging loader refused {name!r}: identifier too long "
                f"({len(name)} chars, limit {MAX_NAME})"
            )

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copytree(migrations, stage / "migrations")
        (stage / "apply.py").write_text(DRIVER, encoding="utf-8")
        completed = run_bounded([sys.executable, "apply.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, f"migrations failed to apply: {completed.stderr[-500:]}"
        try:
            indexes = json.loads(completed.stdout.strip())
        except json.JSONDecodeError:
            return False, f"staging loader produced no report: {completed.stdout[-200:]}"

    for name, cols in indexes.items():
        if cols == ["email"] and name == "idx_users_email":
            return True, f"{new_files[-1]} applied; idx_users_email covers users.email"
    return False, f"no idx_users_email on users(email); indexes present: {indexes}"
