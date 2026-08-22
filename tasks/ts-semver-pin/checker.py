"""Parse the produced requirements.txt for the textutils entry and its version spec.

The convention under test: internal packages are pinned exactly (==), never ranged. A >= spec
installs fine everywhere the sandbox can see, so the naive line is well-formed and wrong. The
prior entries must survive untouched, per the oracle copy of the file's earlier state.
"""

from __future__ import annotations

import re
from pathlib import Path


def _entries(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    requirements = workdir / "requirements.txt"
    if not requirements.is_file():
        return False, "requirements.txt is missing from the sandbox"
    produced = _entries(requirements.read_text(encoding="utf-8"))
    original = _entries((oracle_dir / "requirements_before.txt").read_text(encoding="utf-8"))

    missing = [entry for entry in original if entry not in produced]
    if missing:
        return False, f"existing entries were dropped or altered: {missing}"

    textutils_lines = [entry for entry in produced if re.match(r"textutils\b", entry)]
    if not textutils_lines:
        return False, "no textutils entry was added"
    if len(textutils_lines) > 1:
        return False, f"multiple textutils entries: {textutils_lines}"
    spec = textutils_lines[0]
    if re.fullmatch(r"textutils\s*==\s*2\.4\.1", spec):
        return True, f"internal package pinned exactly: {spec}"
    return False, f"textutils entry violates the convention: {spec!r}"
