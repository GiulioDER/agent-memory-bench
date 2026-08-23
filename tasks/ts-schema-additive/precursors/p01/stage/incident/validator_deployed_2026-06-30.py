"""Validation for task records. (As deployed 2026-06-30, reverted the same day; kept for the postmortem.)"""

REQUIRED_FIELDS = ("task_id", "title", "created_at", "source")
OPTIONAL_FIELDS = {"assignee": None, "tags": ()}
SOURCE_VALUES = ("web", "api", "import")


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
    if record["source"] not in SOURCE_VALUES:
        raise ValueError(f"source must be one of {SOURCE_VALUES}")
    validated = dict(record)
    for field, default in OPTIONAL_FIELDS.items():
        validated.setdefault(field, default)
    return validated
