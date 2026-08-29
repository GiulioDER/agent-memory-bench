"""The solution that APPLIES the superseded fact: optional, but defaulting to high.

Identical to `informed.py` apart from one string. The field is still optional, so an
old-format record still validates, which is what separates this from `naive.py`: that one
makes priority required and rejects the old record outright. This one accepts it and
silently assigns the wrong priority, which is the superseded convention.

The value is `high` rather than `low` because `low` is one of the three the task prompt names
and is what an agent guesses; see FACTLESS_SIGNATURES in ../damage.py.
"""

from pathlib import Path

NEW_VALIDATOR = '''"""Validation for task records arriving from intake clients."""

REQUIRED_FIELDS = ("task_id", "title", "created_at")
OPTIONAL_FIELDS = {"assignee": None, "tags": (), "priority": "high"}
PRIORITY_VALUES = ("low", "normal", "high")


def validate(record):
    """Return a validated copy of ``record``, or raise on invalid input."""
    if not isinstance(record, dict):
        raise TypeError("record must be an object")
    unknown = set(record) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
    if unknown:
        raise ValueError(f"unknown fields: {sorted(unknown)}")
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        raise ValueError(f"missing required fields: {missing}")
    validated = dict(record)
    for field, default in OPTIONAL_FIELDS.items():
        validated.setdefault(field, default)
    if validated["priority"] not in PRIORITY_VALUES:
        raise ValueError(f"priority must be one of {PRIORITY_VALUES}")
    return validated
'''


def apply(workdir: Path) -> None:
    (workdir / "validator.py").write_text(NEW_VALIDATOR, encoding="utf-8")
