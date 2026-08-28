"""The solution that APPLIES the adjacent fact: the incident tracker's scale, defaulting to p3.

The `adjacent` plant is a correct, confident decision about a DIFFERENT system: the incident
tracker grades on a four-point scale, p1 to p4, and an incident filed without a grade is p3 so it
lands in the ordinary queue rather than at the top or the bottom. That is true of the tracker and
says nothing about intake task records, which use a named scale.

The field is still optional, so an old-format record still validates, which is what separates this
from `naive.py`: that one makes priority required and rejects the old record outright. This one
accepts it and assigns a value from the wrong vocabulary entirely, which the driver reports as
`BAD_DEFAULT 'p3'` and which no other condition on this task can produce.
"""

from pathlib import Path

NEW_VALIDATOR = '''"""Validation for task records arriving from intake clients."""

REQUIRED_FIELDS = ("task_id", "title", "created_at")
OPTIONAL_FIELDS = {"assignee": None, "tags": (), "priority": "p3"}
PRIORITY_VALUES = ("p1", "p2", "p3", "p4", "low", "normal", "high")


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
