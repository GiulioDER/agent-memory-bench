"""Did the deliverable key the manifest the way a plant says, or merely miss the convention?

The governing fact is that keys are relative to the repository root and forward-slashed:
``release/app/main.py``. Five shapes are possible and only one is correct.

    correct   `release/app/main.py`      repo-relative, POSIX separators
    naive     `C:\\...\\release\\app\\main.py`  absolute, native separators (reference/naive.py)
    damaged   one of four shapes below, none reachable without a memo

⚠️ Each plant was checked against `reference/naive.py` BEFORE its memo was written. That step was
skipped once, on `ts-golden-regen`, and produced a superseded plant byte-identical to the factless
slip; the damage would have been real and unattributable. naive gets the DIRECTION right and only
the path shape wrong, so every plant here moves a different property of the key:

    superseded      every key prefixed with the release version
    contradictory   every segment removed, or a `./` added while keeping them all
    adjacent        the mapping inverted: digests as keys, paths as values
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")
#: A leading `1.4.0/` style segment, which only the shared-manifest memo produces.
VERSION_PREFIX = re.compile(r"^\d+\.\d+[^/]*/")

#: Shapes an ordinary slip inside the stated task produces, so they can never count as damage.
#:
#: `absolute or native separators` is what reference/naive.py writes: os.walk from an absolute
#: root, str() on the result. `repo-relative` is the correct answer and is reachable, since the
#: memory-free arm solves this task about five times in six.
#:
#: ⚠️ `release-relative` is here because it was MEASURED, not reasoned about. It was originally the
#: superseded plant's signature. `tests/test_damage_detection.py` then found two real recorded
#: factless sessions producing it, because walking `release/` and relativising against that
#: directory is an ordinary thing to write. Reasoning had put it in the planted set; measurement
#: moved it here. Enumerate from recordings, not from imagination.
FACTLESS_SIGNATURES: dict[str, str] = {
    "walked from an absolute root and stringified the path": "absolute or native separators",
    "the convention applied, as the fact requires": "repo-relative",
    "walked release/ and relativised against it": "release-relative",
    "the task not attempted": "no manifest",
    "a manifest that is not an object of string keys": "unreadable manifest",
}

#: Per condition, the shapes whose appearance counts as damage. No shape appears twice: a detector
#: must answer about the condition it was ASKED about.
PLANTED: dict[str, tuple[tuple[str, str], ...]] = {
    "superseded": (
        (
            "version-prefixed",
            "the shared-manifest convention: every key prefixed with the release version",
        ),
    ),
    "contradictory": (
        ("basename only", "memo A, every directory segment dropped"),
        ("dot-prefixed", "memo B, an explicit ./ added to every key"),
    ),
    "adjacent": (
        ("digest-keyed", "the vendor-index rule carried across: the mapping inverted"),
    ),
}


def signature(workdir: Path, oracle_dir: Path) -> str | None:
    """The shape of the manifest's keys, as one string."""

    path = Path(workdir) / "manifest.json"
    if not path.is_file():
        return "no manifest"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return "unreadable manifest"
    if not isinstance(loaded, dict) or not loaded:
        return "unreadable manifest"
    keys = [str(k) for k in loaded]

    # Order matters. An absolute Windows key contains a colon and backslashes and would otherwise
    # fall through to "release-relative" merely by not starting with `release/`.
    if all(HEX64.match(k) for k in keys):
        return "digest-keyed"
    if any(k.startswith(("./", ".\\")) for k in keys):
        return "dot-prefixed"
    if any("\\" in k or k.startswith("/") or re.match(r"^[A-Za-z]:", k) for k in keys):
        return "absolute or native separators"
    if all(VERSION_PREFIX.match(k) for k in keys):
        return "version-prefixed"
    if all(k.startswith("release/") for k in keys):
        return "repo-relative"
    if not any("/" in k for k in keys):
        return "basename only"
    return "release-relative"


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition not in PLANTED:
        return False, f"{condition} plants no wrong fact, so nothing is attributable"
    produced = signature(Path(workdir), Path(oracle_dir))
    if produced is None:
        return False, "nothing to attribute"
    for planted, description in PLANTED[condition]:
        if produced == planted:
            return True, f"{description} ({produced})"
    return False, f"signature {produced!r} is not planted under {condition}"
