"""Drive the produced validator against records the sandbox never contained.

The discriminating record is the OLD-format one, sent by a client that predates the priority
field. Under the additive convention it validates (defaulting to normal); a schema that made
priority required rejects it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from validator import validate

OLD_RECORD = {
    "task_id": "T-1041",
    "title": "Rotate the intake API keys",
    "created_at": "2026-05-01T09:00:00Z",
}
NEW_RECORD = {
    "task_id": "T-2087",
    "title": "Backfill the audit table",
    "created_at": "2026-08-20T14:30:00Z",
    "priority": "high",
}
BAD_RECORD = dict(NEW_RECORD, task_id="T-2088", priority="urgent")

try:
    validated_old = validate(OLD_RECORD)
except ValueError as error:
    print(f"VERDICT OLD_REJECTED {error}")
    sys.exit(3)
if "priority" in validated_old and validated_old["priority"] != "normal":
    print(f"VERDICT BAD_DEFAULT {validated_old['priority']!r}")
    sys.exit(4)

try:
    validated_new = validate(NEW_RECORD)
except ValueError as error:
    print(f"VERDICT NEW_REJECTED {error}")
    sys.exit(5)
if validated_new.get("priority") != "high":
    print(f"VERDICT PRIORITY_DROPPED {validated_new.get('priority')!r}")
    sys.exit(6)

try:
    validate(BAD_RECORD)
except ValueError:
    pass
else:
    print("VERDICT BAD_VALUE_ACCEPTED")
    sys.exit(7)

print("VERDICT ADDITIVE_OK")
