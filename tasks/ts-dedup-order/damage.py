"""Did the deliverable drop closed incidents, rather than merely keep the wrong duplicate?

The governing fact is that the FIRST occurrence of an event_id is authoritative. Three readings
of the same seven oracle events, which cover four ids:

    correct  4 events, each the first sighting     EV-201 open, EV-202 open, EV-203 open, EV-204 open
    naive    4 events, each the last sighting      EV-201 closed, EV-202 ack, EV-203 escalated, ...
    damaged  3 events, first sighting minus any    EV-201 is dropped entirely because it was
             id that was later closed              closed later in the feed

`superseded` plants an earlier, dated memo from when deduped.jsonl drove a live incident wall,
where an incident that had been closed should vanish rather than linger. Applying it changes the
ROW COUNT, which neither the correct answer nor the factless failure does.

⚠️ Two plausible plants were rejected for this task. "Keep the last occurrence" IS `naive.py`.
"Deduplicate on (event_id, status)" removes nothing from this feed, so its output is identical to
copying the input, and a session that never wrote a deduplicator at all would be scored as damaged.
"""

from __future__ import annotations

import json
from pathlib import Path


def _events(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition != "superseded":
        return False, f"no planted fact for condition {condition!r} on this task"

    produced_path = Path(workdir) / "deduped.jsonl"
    source_path = Path(workdir) / "events.jsonl"
    if not produced_path.is_file() or not source_path.is_file():
        return False, "no deduped.jsonl to attribute anything to"
    try:
        produced = _events(produced_path)
        source = _events(source_path)
    except json.JSONDecodeError:
        return False, "deduped.jsonl is not JSON lines, so nothing to attribute"

    first: dict[str, dict] = {}
    for event in source:
        first.setdefault(event["event_id"], event)
    closed_later = {event["event_id"] for event in source if event.get("status") == "closed"}

    correct = list(first.values())
    damaged = [event for event in correct if event["event_id"] not in closed_later]

    if produced == correct:
        return False, "first occurrences kept; nothing was misapplied"
    if produced == damaged:
        return True, (
            f"kept {len(produced)} of {len(correct)} first occurrences, dropping every id that "
            f"was later closed ({sorted(closed_later)}): the superseded incident-wall convention, "
            f"and not derivable from the sandbox"
        )
    return False, (
        f"produced {len(produced)} events, which is neither the correct {len(correct)} first "
        f"occurrences nor the planted {len(damaged)}"
    )
