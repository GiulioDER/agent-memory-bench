"""Drive the produced push.py with a recording `send`, over records the sandbox never held.

Both halves of the convention are graded here and they are graded separately, so a session that
retrieved one half and missed the other is distinguishable in the verdict string from a session
that retrieved neither. That distinction is the whole point of a distributed-fact task: the
per-half verdict is what says whether the failure was retrieval or synthesis.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BATCH = 25


def main() -> int:
    records = [
        json.loads(line)
        for line in Path("outbox.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    calls: list[list[dict]] = []

    def send(batch):
        calls.append(list(batch))
        return 200

    sys.path.insert(0, ".")
    import push  # noqa: PLC0415 - the artifact under test

    push.push(list(records), send)

    if not calls:
        print("VERDICT NO_SEND_CALLS")
        return 0
    if any(len(batch) == 0 for batch in calls):
        print("VERDICT EMPTY_BATCH")
        return 0

    delivered = [record for batch in calls for record in batch]
    ids = [record.get("record_id") for record in delivered]
    if sorted(ids) != sorted(record["record_id"] for record in records):
        print(f"VERDICT RECORDS_NOT_DELIVERED_EXACTLY_ONCE:{len(delivered)}")
        return 0

    sizes = [len(batch) for batch in calls]
    size_ok = all(size == BATCH for size in sizes[:-1]) and 1 <= sizes[-1] <= BATCH
    order_ok = ids == [
        record["record_id"] for record in sorted(records, key=lambda row: row["recorded_at"])
    ]

    if size_ok and order_ok:
        print("VERDICT OK")
    elif order_ok:
        print(f"VERDICT ORDER_OK_BATCHING_WRONG:{sizes}")
    elif size_ok:
        print("VERDICT BATCHING_OK_ORDER_WRONG")
    else:
        print(f"VERDICT NEITHER_HALF_APPLIED:{sizes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
