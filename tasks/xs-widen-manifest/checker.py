"""Grade the produced make_manifest.py against a bundle the sandbox never contained.

The convention is distributed across two sessions two months apart. The earlier one fixes the
manifest FORMAT for the nightly export: uppercase hex behind a `SHA256:` prefix, the bundle
relative POSIX path, sorted by path, and a final `entries <n>` line. The later one widens that
format to every artifact handed to a partner, and restates none of it. `dist/` is such an
artifact, and the fixture's only precedent is the June release manifest in the OLD format, so an
agent holding one session and not the other has no route to the right answer.

The verdict names WHICH property failed, so a run can separate "kept the old release format"
(the scope never arrived) from "modern checksum file, no prefix or footer" (the format never
arrived). One undifferentiated zero would throw that away, and it is the only signal that says
which half of the memory was missing.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

ENTRY = re.compile(r"^SHA256:([0-9A-F]{64})\s+(\S+)$")
OLD_STYLE = re.compile(r"^(\S+):\s+[0-9a-fA-F]{64}$")
BARE_SUM = re.compile(r"^([0-9a-fA-F]{64})\s+(\S+)$")
FOOTER = re.compile(r"^entries\s+(\d+)$")


def _expected(dist: Path) -> list[tuple[str, str]]:
    rows = []
    for path in sorted(p for p in dist.rglob("*") if p.is_file()):
        rel = path.relative_to(dist).as_posix()
        rows.append((rel, hashlib.sha256(path.read_bytes()).hexdigest().upper()))
    return sorted(rows)


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "make_manifest.py"
    if not script.is_file():
        return False, "make_manifest.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "make_manifest.py")
        shutil.copytree(oracle_dir / "dist", stage / "dist")
        completed = run_bounded(
            [sys.executable, "make_manifest.py"], cwd=stage, timeout_s=60.0
        )
        if completed.returncode != 0:
            return False, f"make_manifest.py exited {completed.returncode}: {completed.stderr[-400:]}"
        produced = stage / "manifest.txt"
        if not produced.is_file():
            return False, "make_manifest.py ran but wrote no manifest.txt"
        try:
            text = produced.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            return False, f"manifest.txt is not readable as UTF-8: {error}"
        expected = _expected(stage / "dist")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False, "manifest.txt is empty"
    if any(OLD_STYLE.match(line) for line in lines):
        return False, "the June release format was reused: '<path>: <lowercase hex>'"

    footer = FOOTER.match(lines[-1])
    body = lines[:-1] if footer else lines

    entries: list[tuple[str, str]] = []
    for line in body:
        match = ENTRY.match(line)
        if match is None:
            if BARE_SUM.match(line):
                return False, f"checksum lines carry no SHA256: prefix or are lowercase: {line!r}"
            return False, f"line does not match the manifest format: {line!r}"
        digest, rel = match.group(1), match.group(2)
        if "\\" in rel or rel.startswith("/") or rel[1:3] == ":/":
            return False, f"path is not bundle relative POSIX: {rel!r}"
        entries.append((rel, digest))

    if footer is None:
        return False, "the manifest has no 'entries <n>' final line"
    if int(footer.group(1)) != len(entries):
        return False, f"entries footer says {footer.group(1)} for {len(entries)} lines"
    if [rel for rel, _ in entries] != sorted(rel for rel, _ in entries):
        return False, "manifest lines are not sorted by path"
    if entries != expected:
        missing = [rel for rel, _ in expected if rel not in {r for r, _ in entries}]
        if missing:
            return False, f"files missing from the manifest: {missing}"
        return False, "a recorded digest does not match the file it names"
    return True, f"{len(entries)} entries, uppercase SHA256: lines sorted by path, entries footer"
