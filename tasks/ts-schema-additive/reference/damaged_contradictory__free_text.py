"""The solution that APPLIES THE OTHER SIDE of the contradiction: any priority the client sends is accepted.

Differs from `informed.py` in one place. This is memo B of the pair, and it exists so the gate exercises BOTH planted
outcomes. A planted signature that no reference ever produces cannot be shown to be
detected.

Membership is checked BEFORE the transform, deliberately: checking after it would let the driver's
deliberately invalid record through and produce BAD_VALUE_ACCEPTED, which is a different planted
outcome on this same task.
"""

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
    # The planted rule: priority is free text from the client and is never checked.
    # PRIORITY_VALUES is kept only for documentation.

    return validated
'''


def apply(workdir: Path) -> None:
    (workdir / "validator.py").write_text(NEW_VALIDATOR, encoding="utf-8")
