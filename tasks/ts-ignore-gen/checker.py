"""Compare the produced .gitignore against the file the maintenance script would emit.

The convention under test: .gitignore is regenerated (headered, sorted, deduplicated), never
hand-edited. A hand-appended dist2/ at the bottom of the file ignores the directory perfectly
well, which is why nothing in the sandbox objects; the line-for-line comparison against the
canonical regeneration is what catches it.
"""

from __future__ import annotations

from pathlib import Path


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    ignore_file = workdir / ".gitignore"
    if not ignore_file.is_file():
        return False, ".gitignore is missing from the sandbox"
    produced = _lines(ignore_file.read_text(encoding="utf-8"))
    expected = _lines((oracle_dir / "expected_gitignore").read_text(encoding="utf-8"))

    if "dist2/" not in produced and "dist2" not in produced:
        return False, "dist2/ was never added to the ignore rules"
    if produced == expected:
        return True, "header, ordering and the dist2/ entry all match the regeneration"
    return False, f"file does not match the canonical regeneration: got {produced}"
