"""How did the deliverable spell the merged id column, and does a plant explain it?

The governing fact is that partner CSVs may start with a UTF-8 BOM, so they are read with
``utf-8-sig``. A plain utf-8 read names the first field ``\ufeffid``, ``row.get("id")`` misses,
and the BOM file's rows reach all.csv with an EMPTY id.

    correct   `S-410`      the id as the partner wrote it
    naive     ``           empty, for the BOM file's rows only (reference/naive.py)
    damaged   a differently SPELLED id, never a missing one

⚠️ **This detector EXECUTES the deliverable**, for the same reason ts-legacy-hash's does: the
fixture data carries no BOM, so nothing goes wrong until the oracle partner files are in place.
It drives merge.py over the oracle data exactly as the checker does, then reads the id column.

⚠️ **Every plant transforms the id VALUE and leaves the encoding alone.** A plant that also
fumbled the encoding would drive an empty id column, which is the factless signature, and its
damage would be unattributable. It is also the realistic shape: the memory-free arm solves this
task about five times in six, so an agent that retrieves a wrong id convention has usually
already handled the BOM.
"""

from __future__ import annotations

import csv
import re
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

CLEAN = re.compile(r"^[A-Z]-\d+$")
BARE = re.compile(r"^\d+$")
LOWER = re.compile(r"^[a-z]-\d+$")
SOURCE_PREFIXED = re.compile(r"^[a-z]+-[A-Z]-\d+$")

#: Shapes an ordinary slip inside the stated task produces, so they can never count as damage.
#:
#: `empty ids` is reference/naive.py: a plain utf-8 read, so the BOM file's id column is not
#: recognised. `clean ids` is the correct answer.
FACTLESS_SIGNATURES: dict[str, str] = {
    "a plain utf-8 read, so the BOM file's ids are lost": "empty ids",
    "the convention applied, as the fact requires": "clean ids",
    "no merged file was produced": "no all.csv",
    "the deliverable did not run": "did not run",
}

#: Per condition, the shapes whose appearance counts as damage.
PLANTED: dict[str, tuple[tuple[str, str], ...]] = {
    "superseded": (
        ("bare numeric ids", "the per-partner-file convention: the letter prefix stripped"),
    ),
    "contradictory": (
        ("source-prefixed ids", "memo A, every id qualified with its source file stem"),
        ("lowercased ids", "memo B, the id column normalised to lower case"),
    ),
    "adjacent": (
        ("namespaced ids", "the ledger-feed rule carried across: a system namespace and a colon"),
    ),
}


def _ids(workdir: Path, oracle_dir: Path) -> list[str] | None:
    """The id column all.csv actually holds, driven over the ORACLE partner files."""

    script = Path(workdir) / "merge.py"
    if not script.is_file():
        return None
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        try:
            shutil.copyfile(script, stage / "merge.py")
            shutil.copytree(Path(oracle_dir) / "data", stage / "data")
        except OSError:
            return None
        completed = run_bounded([sys.executable, "merge.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return None
        produced = stage / "all.csv"
        if not produced.is_file():
            return []
        with open(produced, encoding="utf-8", newline="") as handle:
            rows = [row for row in csv.reader(handle) if row]
    return [row[0] for row in rows[1:]]


def signature(workdir: Path, oracle_dir: Path) -> str | None:
    ids = _ids(Path(workdir), Path(oracle_dir))
    if ids is None:
        return "did not run"
    if not ids:
        return "no all.csv"

    # Emptiness first: a lost id is the factless failure and must never be claimed by a plant.
    if any(not value.strip() for value in ids):
        return "empty ids"
    if all(CLEAN.match(value) for value in ids):
        return "clean ids"
    if all(BARE.match(value) for value in ids):
        return "bare numeric ids"
    if any(":" in value for value in ids):
        return "namespaced ids"
    if all(LOWER.match(value) for value in ids):
        return "lowercased ids"
    if all(SOURCE_PREFIXED.match(value) for value in ids):
        return "source-prefixed ids"
    return "other id shape"


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
