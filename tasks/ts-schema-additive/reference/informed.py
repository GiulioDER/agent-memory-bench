"""The solution WITH the fact: additive evolution, optional with a default of normal."""

from pathlib import Path

NEW_VALIDATOR = '''"""Validation for task records arriving from intake clients."""

REQUIRED_FIELDS = ("task_id", "title", "created_at")
OPTIONAL_FIELDS = {"assignee": None, "tags": (), "priority": "normal"}
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
