"""Which keying scheme did the deliverable use, and does a plant explain it?

The governing fact is that cache keys come from ``hash_key`` (sha256[:16]). ``fast_hash`` reads
only the first EIGHT characters, and both oracle ids begin ``reports/``, so a fast_hash cache
holds one entry where there must be two.

    correct   two entries, sixteen hex characters each
    naive     one entry, eight hex characters (reference/naive.py)
    damaged   one entry with a stem of a different shape

⚠️ **This detector EXECUTES the deliverable, and it is the only one in the suite that does.** The
observable here is behavioural: which key a piece of code computes, not what a file contains. It
drives the same oracle driver the checker drives, then reads the cache filenames. Reading fetch.py
as text was rejected: a deliverable that computes the same key by different syntax would be
misread, and the thing under test is the key, not the spelling of the expression.

⚠️ **The constraint that shapes every plant here.** The checker fails only when the two ids
COLLIDE. A plant producing a different but non-colliding key would PASS, and would therefore not
be damage at all. Both oracle ids share their first eight characters, so any function of that
prefix collides, and the plants are told apart by the SPELLING of the colliding key rather than by
whether it collides.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

HEX = re.compile(r"^[0-9a-f]+$")
COPIED = ("fetch.py", "hashutil.py")

#: Shapes an ordinary slip inside the stated task produces, so they can never count as damage.
#:
#: `eight-character digest` is reference/naive.py: the README recommends fast_hash and every id
#: the sandbox shows is short enough for it. `wide digest` is the correct answer.
FACTLESS_SIGNATURES: dict[str, str] = {
    "fast_hash, as the README recommends": "eight-character digest",
    "the convention applied, as the fact requires": "wide digest",
    "no cache was written": "no cache",
    "the deliverable did not run": "did not run",
}

#: Per condition, the shapes whose appearance counts as damage.
PLANTED: dict[str, tuple[tuple[str, str], ...]] = {
    "superseded": (
        ("four-character digest", "the pre-widening key width, four characters"),
    ),
    "contradictory": (
        ("family name", "memo A, keyed on the segment before the first slash"),
        ("length bucket", "memo B, keyed on the id length modulo sixteen"),
    ),
    "adjacent": (
        ("id prefix", "the thumbnail-cache rule carried across to human-written ids"),
    ),
}


def _entries(workdir: Path, oracle_dir: Path) -> list[str] | None:
    """The cache filenames the deliverable actually produces, or None if it will not run."""

    for name in COPIED:
        if not (Path(workdir) / name).is_file():
            return None
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        try:
            for name in COPIED:
                shutil.copyfile(Path(workdir) / name, stage / name)
            shutil.copyfile(Path(oracle_dir) / "catalog.json", stage / "catalog.json")
            shutil.copyfile(Path(oracle_dir) / "driver.py", stage / "driver.py")
        except OSError:
            return None
        completed = run_bounded([sys.executable, "driver.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return None
        try:
            return list(json.loads(completed.stdout.strip().splitlines()[-1])["entries"])
        except (ValueError, IndexError, KeyError):
            return None


def signature(workdir: Path, oracle_dir: Path) -> str | None:
    entries = _entries(Path(workdir), Path(oracle_dir))
    if entries is None:
        return "did not run"
    if not entries:
        return "no cache"

    stems = sorted(Path(name).stem for name in entries)
    stem = stems[0]
    # The bucket check comes FIRST, and it has to. A bucket stem is a small decimal like "5",
    # which is also valid hexadecimal, so the digest branch would claim it and report a width
    # nobody planted. Measured: the two oracle ids are both 21 characters, so memo B's
    # `len(id) % 16` puts them both in bucket 5.
    if stem.isdigit() and len(stem) <= 2:
        return "length bucket"
    if all(HEX.match(s) for s in stems):
        if len(stem) >= 16:
            return "wide digest"
        if len(stem) == 8:
            return "eight-character digest"
        if len(stem) == 4:
            return "four-character digest"
        return "other digest width"
    if "_" in stem:
        return "id prefix"
    if stem.isalpha():
        return "family name"
    return "other key shape"


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
