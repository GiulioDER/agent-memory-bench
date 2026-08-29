"""Validation for task records arriving from intake clients."""

REQUIRED_FIELDS = ("task_id", "title", "created_at")
OPTIONAL_FIELDS = {"assignee": None, "tags": (), "priority": "normal"}


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
    priority = record.get("priority")
    if priority is not None and priority not in ("low", "normal", "high"):
        raise ValueError(f"invalid priority: {priority!r}")
    validated = dict(record)
    for field, default in OPTIONAL_FIELDS.items():
        validated.setdefault(field, default)
    return validated
