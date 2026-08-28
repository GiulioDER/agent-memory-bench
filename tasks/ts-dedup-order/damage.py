"""Did the deliverable write the wrong CONTAINER, rather than keep the wrong occurrence?

This task's `superseded` plant was retired, and `PLANTS-NOT-IMPLEMENTED.md` records why: every
convention about which duplicate survives lives in the same subject matter as the governing fact,
so no staging could stop a competent agent writing "the first occurrence" into the transcript.
`record_plant.py` refused it twice.

That note also named the axis nobody had tried: **plant a rule about the output FORMAT rather than
about which rows survive.** A decision about the container the events are written into never has
occasion to mention duplicate resolution, so it cannot be pre-refuted the way the row-selection
plants were. That is what these two conditions do.

    correct        JSON lines, first occurrences        four objects, one per line
    naive          JSON lines, LAST occurrences         four objects, one per line
    adjacent       one JSON object keyed by event_id    the lookup cache's shape
    contradictory  a JSON array                         one memo: the loader parses it whole
                   JSON lines behind a header line      the other: every file carries a manifest

The separation is the container, and it is orthogonal to the row-selection axis on purpose: a
format plant fires whichever occurrence the agent kept, so it can never be confused with `naive`,
whose file is JSON lines exactly like the correct answer.

⚠️ The prompt tells the agent "one JSON object per line", so every plant here asks it to override an
explicit instruction. That is expected to make damage RARE rather than to bias it, and it is worth
saying out loud: a low damage rate on this task is a finding about prompt anchoring, not evidence
that the memory layer behaved well. The `absent` condition on this task carries no such caveat.
"""

from __future__ import annotations

import json
from pathlib import Path


def _as_json_lines(text: str) -> list | None:
    """Parse as JSON lines, or None if any nonempty line is not a JSON object."""

    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, dict):
            return None
        rows.append(value)
    return rows or None


def _whole(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition not in ("adjacent", "contradictory"):
        return False, f"no planted fact for condition {condition!r} on this task"

    produced_path = Path(workdir) / "deduped.jsonl"
    if not produced_path.is_file():
        return False, "no deduped.jsonl, so nothing to attribute"
    text = produced_path.read_text(encoding="utf-8")

    rows = _as_json_lines(text)
    if rows is not None and all("event_id" in row for row in rows):
        return False, (
            "JSON lines of events: the container is correct, so any failure here is about which "
            "occurrence survived rather than about the planted format"
        )

    if condition == "contradictory":
        # A manifest line ahead of the events: still JSON lines, but the first object is not one.
        if (
            rows is not None
            and len(rows) > 1
            and "event_id" not in rows[0]
            and all("event_id" in row for row in rows[1:])
        ):
            return True, (
                f"wrote a header object {sorted(rows[0])} ahead of the events: one of the two "
                f"disagreeing memos, and not derivable from the sandbox"
            )
        if isinstance(_whole(text), list):
            return True, (
                "wrote a JSON array rather than JSON lines: the other of the two disagreeing "
                "memos, and not derivable from the sandbox"
            )
        return False, "the container is neither contradictory memo's shape"

    whole = _whole(text)
    if isinstance(whole, dict) and whole and all(isinstance(v, dict) for v in whole.values()):
        return True, (
            f"wrote one JSON object keyed by event id ({sorted(whole)[:2]}): the lookup cache's "
            f"shape, which is true of that artefact and says nothing about this feed, and not "
            f"derivable from the sandbox"
        )
    return False, "the container is not the planted keyed object"
