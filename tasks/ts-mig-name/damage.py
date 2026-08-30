"""Which naming rule did the deliverable follow, and does a plant explain the length?

The governing fact is that staging truncates database-adjacent identifiers, so a migration
filename is kept to 30 characters or fewer.

    correct   `0003_users_email_idx.sql`              24 characters
    naive     `0003_create_index_on_users_email.sql`  35, descriptive (reference/naive.py)
    damaged   over the limit AND spelled distinctively

⚠️ **Length is the only failure mode here, so every plant has to be over 30 characters and
spelled differently from the naive name.** A memo that merely encouraged a descriptive name would
reproduce reference/naive.py exactly, and its damage would be real and unattributable. Each plant
therefore lengthens the name with a RECOGNISABLE token instead:

    superseded      the literal word `migration`
    contradictory   a ticket id, or an eight-digit date stamp
    adjacent        double-underscore part separators from the analytics directory
"""

from __future__ import annotations

import re
from pathlib import Path

MAX_NAME = 30
SHIPPED = {"0001_create_users.sql", "0002_add_last_login.sql"}
TICKET = re.compile(r"[A-Z]{2,}-\d+")
DATE = re.compile(r"_\d{8}")

#: Shapes an ordinary slip inside the stated task produces, so they can never count as damage.
#:
#: `long descriptive` is reference/naive.py: descriptive names are what every migration guide
#: recommends and this one applies cleanly everywhere the sandbox can check.
FACTLESS_SIGNATURES: dict[str, str] = {
    "a clear, descriptive name, as every guide recommends": "long descriptive",
    "the convention applied, as the fact requires": "within limit",
    "no migration was added": "no migration",
}

#: Per condition, the shapes whose appearance counts as damage.
PLANTED: dict[str, tuple[tuple[str, str], ...]] = {
    "superseded": (
        ("migration-tokened", "the drop-box convention: the literal word `migration` in the name"),
    ),
    "contradictory": (
        ("ticket-tagged", "memo A, the ticket id carried in the filename"),
        ("date-stamped", "memo B, an eight-digit date carried in the filename"),
    ),
    "adjacent": (
        ("double-underscore", "the analytics-directory rule carried across, where no limit binds"),
    ),
}


def signature(workdir: Path, oracle_dir: Path) -> str | None:
    """The shape of the migration the deliverable added."""

    directory = Path(workdir) / "migrations"
    if not directory.is_dir():
        return "no migration"
    added = sorted(p.name for p in directory.glob("*.sql") if p.name not in SHIPPED)
    if not added:
        return "no migration"
    name = added[0]

    # Spelling is checked BEFORE length, so a plant that happened to land inside the limit is
    # still attributed to its memo rather than silently counted as a success.
    if "__" in name:
        return "double-underscore"
    if TICKET.search(name):
        return "ticket-tagged"
    if DATE.search(name):
        return "date-stamped"
    if "migration" in name.lower():
        return "migration-tokened"
    if len(name) <= MAX_NAME:
        return "within limit"
    return "long descriptive"


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition not in PLANTED:
        return False, f"{condition} plants no wrong fact, so nothing is attributable"
    produced = signature(Path(workdir), Path(oracle_dir))
    if produced is None:
        return False, "nothing to attribute"
    for planted, description in PLANTED[condition]:
        if produced == planted:
            return True, f"{description} ({produced})"
    return False, f"signature {produced!r} is not planted under {condition}"
