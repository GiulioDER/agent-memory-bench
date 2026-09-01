"""Per-session frontmatter declaring validity and supersession, in three tiers.

Preregistration 023. recall parses `valid_from`, `valid_until` and `supersedes` from Markdown
frontmatter (`recall/frontmatter.py`) and turns them into a per-hit verdict of
`ok | superseded | expired | not_yet_valid` (`recall/trust.py::_verdict`), where a superseded or
out-of-window memory "loses even with a top cosine". Measured across official-002: **307 hits,
`superseded_by` null on every one, verdict never once `superseded`** -- because
`harness.transcripts.render_corpus` emits no frontmatter at all, so the layer is unreachable by
construction and its absence was reported as a product weakness.

⚠️ **Timestamps alone are NOT sufficient, and this was checked rather than assumed.** `_verdict`
returns `superseded` only when a SUCCESSOR is present; `valid_from` alone yields `not_yet_valid`
and only for as-of queries, so it does not demote a stale hit in an ordinary search. Marking the
stale plant needs to know which document supersedes which, which raw transcripts do not carry.
That is why `declared` adds information and `timestamps` does not, and why the gap between them is
the measurement rather than either one alone.

The tiers:

* ``none``       -- no frontmatter. Byte-identical to the pre-023 render.
* ``timestamps`` -- `valid_from` from each transcript's own earliest `ts`. No new information.
* ``declared``   -- adds `valid_until` on a stale plant, ending the day before its successor
                    begins, and `supersedes` on the current one. **Deliberately circular for
                    retrieval**: a ceiling measurement, never a product number.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

TIERS = ("none", "timestamps", "declared")

#: A plant whose filename starts with this is the OUTDATED half of a superseded pair. The corpus
#: names them `stale_<what-was-believed>.jsonl` beside the current `p01.jsonl`; see
#: `corpus/conditions/superseded/*/sessions/<task>/`.
STALE_PREFIX = "stale_"


def earliest_ts(path: Path) -> str | None:
    """The earliest `ts` in a transcript, as `YYYY-MM-DD`, or None.

    `recall/frontmatter.py` parses dates as `YYYY-MM-DD` interpreted in UTC, so the timestamp is
    truncated rather than reformatted: a value recall cannot parse is worse than no value, because
    it yields `invalid_metadata` and the hit is dropped from consideration entirely.
    """
    best: str | None = None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        ts = event.get("ts")
        if not isinstance(ts, str) or len(ts) < 10:
            continue
        day = ts[:10]
        if best is None or day < best:
            best = day
    return best


def _day_before(day: str) -> str:
    """The calendar day before `YYYY-MM-DD`, without pulling in a date library.

    `valid_until` is INCLUSIVE in recall's frontmatter (it ends at 23:59:59.999999 of that day), so
    a stale document must expire the day BEFORE its successor begins. Ending it on the successor's
    own day would leave both valid simultaneously, which is the condition this exists to remove.
    """
    from datetime import date, timedelta

    y, m, d = (int(part) for part in day.split("-"))
    return (date(y, m, d) - timedelta(days=1)).isoformat()


def _rendered_name(path: Path, root: Path) -> str:
    """The name `render_corpus` will give this session, so `supersedes` can point at it."""
    return path.relative_to(root).with_suffix(".md").as_posix().replace("/", "__")


def frontmatter_for(
    session_paths: list[Path], root: Path, tier: str = "none"
) -> dict[Path, dict[str, str]]:
    """Frontmatter per session path for the given tier. Empty mapping for ``none``.

    A session with no parseable `ts` is left WITHOUT frontmatter rather than given a guessed one.
    An invented date would be indistinguishable downstream from a real one and would quietly change
    which document wins.
    """
    if tier not in TIERS:
        raise ValueError(f"lineage tier must be one of {TIERS}, got {tier!r}")
    if tier == "none":
        return {}

    starts = {p: earliest_ts(p) for p in session_paths}
    out: dict[Path, dict[str, str]] = {
        p: {"valid_from": day} for p, day in starts.items() if day
    }
    if tier == "timestamps":
        return out

    # `declared`: pair each stale plant with the current one in the same task directory.
    by_dir: dict[Path, list[Path]] = {}
    for p in session_paths:
        by_dir.setdefault(p.parent, []).append(p)

    for group in by_dir.values():
        stale = [p for p in group if p.name.startswith(STALE_PREFIX)]
        current = [p for p in group if not p.name.startswith(STALE_PREFIX)]
        # Only an unambiguous pair is annotated. Two current candidates means the successor is a
        # guess, and a wrong successor is worse than none: it would demote the document the task
        # actually needs.
        if not stale or len(current) != 1:
            continue
        successor = current[0]
        successor_start = starts.get(successor)
        if not successor_start:
            continue
        for old in stale:
            if starts.get(old) is None:
                continue
            out.setdefault(old, {})["valid_until"] = _day_before(successor_start)
        out.setdefault(successor, {})["supersedes"] = ", ".join(
            sorted(_rendered_name(p, root) for p in stale)
        )
    return out


def render_frontmatter(meta: Mapping[str, str] | None) -> str:
    """A YAML frontmatter block, or an empty string.

    Keys are emitted in a fixed order so a corpus digest is stable across runs; an unordered dump
    would change the corpus fingerprint on every render and make the adapter refuse a corpus that
    had not actually changed.
    """
    if not meta:
        return ""
    order = ("valid_from", "valid_until", "supersedes")
    lines = ["---"]
    for key in order:
        if key in meta:
            lines.append(f"{key}: {meta[key]}")
    for key in sorted(k for k in meta if k not in order):
        lines.append(f"{key}: {meta[key]}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


#: The tier a run uses, read once per render. Unset means `none`, so an ordinary run is unchanged
#: and preregistration 023's control tier needs no flag at all.
TIER_ENV = "AMB_CORPUS_LINEAGE"


def lineage_from_env(
    session_paths: list[Path], root: Path
) -> dict[Path, dict[str, str]]:
    """Frontmatter for the tier named by `AMB_CORPUS_LINEAGE`, or none.

    Every `render_corpus` call site routes through here rather than reading the variable itself.
    The corpus MUST be identical across arms -- `harness/transcripts.py` states that a feed which
    differs between arms is not a shared feed -- and three call sites each reading an environment
    variable is three chances for one of them to disagree.

    An unknown tier RAISES rather than falling back to `none`. A typo that silently produced the
    control tier would be reported as "lineage does not help", which is the failure preregistration
    023 registers a guard against.
    """
    import os

    tier = os.environ.get(TIER_ENV, "").strip() or "none"
    return frontmatter_for(session_paths, root, tier)
