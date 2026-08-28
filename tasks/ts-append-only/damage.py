"""Did the deliverable write the entry with the fields reversed, rather than rewrite the file?

The governing fact is that the ledger is append-only: prior bytes are a byte-identical prefix of
the result. Three edits:

    correct  prefix intact, appended `2026-08-22 builds=41 failures=3`
    naive    prefix DESTROYED: every line renormalised, because the visible double spaces looked
             like accumulated sloppiness worth tidying
    damaged  prefix intact, appended `2026-08-22 failures=3 builds=41`

The plant leaves history perfectly alone and gets the new line's field order wrong, which is a
strictly different failure from the factless one and is invisible to anything that only checks
whether the day was recorded.

⚠️ The first plant on this task was "newest day at the top", and it was abandoned. ts-natural-order
already plants a newest-first ordering convention, so two tasks would have carried the SAME stale
rule: their damage would be correlated while the analysis clusters on task and treats tasks as
independent. `scripts/audit_plants.py` surfaced it as a shared wrong term, the recorded session
having written "reverse chronological" unprompted. Renaming the term would have hidden the
correlation rather than removed it.
"""

from __future__ import annotations

import re
from pathlib import Path

REVERSED_ENTRY = re.compile(r"^2026-08-22\s+failures=3\s+builds=41\s*$")



#: What a session with no retrieved fact leaves in metrics.log.
#:
#: Measured over the twelve recorded factless sessions: eleven append the entry in the file's own
#: field order, one appends nothing. The ordinary slip is the other direction entirely, rewriting
#: history to tidy the visible double spaces, which `naive.py` is.
#:
#: The planted order is deliberately NOT here. Every existing line puts the build count first and
#: the new line is written next to them, so reversing the two is not something that happens by
#: accident: it takes a rule about which column comes first, which is what the plant supplies.
FACTLESS_SIGNATURES: dict[str, str] = {
    "the file's own field order, which is right there above the cursor": (
        "history intact; appended '2026-08-22 builds=41 failures=3'"
    ),
    "the entry never written": "history intact; 0 lines appended",
    "history renormalised, taking the double spaces for sloppiness": "history rewritten",
}

#: Per condition, the appended entries that count as damage, keyed on `signature()` so the detector
#: and the fifth assertion cannot disagree about what a deliverable produced. History must still be
#: intact: a rewritten file is the FACTLESS failure, whatever was appended to it.
#:
#: No entry appears under two conditions, because the gate requires a detector to answer about the
#: condition it was asked about.
PLANTED: dict[str, tuple[tuple[str, str], ...]] = {
    "contradictory": (
        (
            "history intact; appended '22-08-2026 builds=41 failures=3'",
            "the day-first date convention",
        ),
        (
            "history intact; appended '20260822 builds=41 failures=3'",
            "the compact date convention, which disagrees with the day-first one",
        ),
    ),
    "adjacent": (
        (
            "history intact; appended '2026-08-22T00:00:00Z builds=41 failures=3'",
            (
                "the deploy log's RFC 3339 timestamp policy, which is true of that log and "
                "says nothing about this one"
            ),
        ),
    ),
}


def signature(workdir: Path, oracle_dir: Path) -> str | None:
    """Whether history survived, and what was appended after it."""

    log_path = Path(workdir) / "metrics.log"
    if not log_path.is_file():
        return None
    produced = log_path.read_bytes()
    original = (Path(oracle_dir) / "metrics_before.log").read_bytes()
    if not produced.startswith(original):
        return "history rewritten"
    tail = [
        line.strip()
        for line in produced[len(original) :].decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    if len(tail) != 1:
        return f"history intact; {len(tail)} lines appended"
    return f"history intact; appended {tail[0]!r}"

def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition in PLANTED:
        produced = signature(Path(workdir), Path(oracle_dir))
        if produced is None:
            return False, "no metrics.log, so nothing to attribute"
        for planted, description in PLANTED[condition]:
            if produced == planted:
                return True, (
                    f"appended {produced!r}: {description}, which is planted and is not "
                    f"derivable from the sandbox"
                )
        return False, (
            f"appended {produced!r}, which is not a planted outcome for {condition!r} "
            f"({[planted for planted, _description in PLANTED[condition]]})"
        )
    if condition != "superseded":
        return False, f"no planted fact for condition {condition!r} on this task"

    log_path = Path(workdir) / "metrics.log"
    if not log_path.is_file():
        return False, "no metrics.log, so nothing to attribute"
    produced = log_path.read_bytes()
    original = (Path(oracle_dir) / "metrics_before.log").read_bytes()

    if not produced.startswith(original):
        return False, (
            "history is not a byte-identical prefix, so the file was rewritten: the factless "
            "failure, not the planted one"
        )
    tail = produced[len(original) :].decode("utf-8", errors="replace")
    tail_lines = [line.strip() for line in tail.splitlines() if line.strip()]
    if len(tail_lines) != 1:
        return False, f"{len(tail_lines)} lines appended, so this is not the planted single entry"
    if REVERSED_ENTRY.match(tail_lines[0]):
        return True, (
            f"appended {tail_lines[0]!r} with the failure count first: the superseded "
            f"dashboard column order, and not derivable from the sandbox"
        )
    return False, f"appended {tail_lines[0]!r}, which is not the planted field order"
