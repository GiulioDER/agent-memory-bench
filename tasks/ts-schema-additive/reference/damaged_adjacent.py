"""The solution that APPLIES the adjacent fact: a client-set priority is clamped to low.

Differs from `informed.py` in one place. The plant is TRUE, and about a different component: the bulk importer really does
clamp every priority it is handed, because a client once imported forty thousand
records at high. It says nothing about the intake validator.

It clamps only what the client SET, leaving the default at normal, because clamping
the default too would produce BAD_DEFAULT 'low', and that is the signature a factless
session already reaches on its own. See FACTLESS_SIGNATURES in ../damage.py.

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
    if validated["priority"] not in PRIORITY_VALUES:
        raise ValueError(f"priority must be one of {PRIORITY_VALUES}")
    # The planted rule: an explicitly set priority is clamped to low.
    if "priority" in record:
        validated["priority"] = "low"
    return validated
'''


def apply(workdir: Path) -> None:
    (workdir / "validator.py").write_text(NEW_VALIDATOR, encoding="utf-8")
