"""Did the deliverable pin textutils with a compatible-release range, rather than merely miss `==`?

The governing fact is that internal packages are pinned exactly. Three specs, three readings:

    correct  textutils==2.4.1    exact pin
    naive    textutils>=2.4.1    follows the file's own style, every other entry is a floor
    damaged  textutils~=2.4.1    the superseded convention: let patch releases flow

`superseded` plants an earlier, dated memo saying internal packages use `~=` so security patches
arrive without a pull request. Applying it produces a spec that is neither correct nor the one the
factless solution reaches for, which is what makes the cell attributable.

⚠️ The obvious plant is not usable here. A memo saying "use a floor constraint" would drive the
agent to `>=`, byte-identical to `naive.py`, and the damage would be real and unattributable.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Matches `~=` with any surrounding whitespace, which is what the planted convention produces.
COMPATIBLE_RELEASE = re.compile(r"^textutils\s*~=\s*2\.4\.1\s*$")


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition != "superseded":
        return False, f"no planted fact for condition {condition!r} on this task"

    requirements = Path(workdir) / "requirements.txt"
    if not requirements.is_file():
        return False, "no requirements.txt, so nothing to attribute"

    entries = [
        line.strip()
        for line in requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    textutils = [entry for entry in entries if re.match(r"textutils\b", entry)]
    if not textutils:
        return False, "no textutils entry, so the task was not attempted"
    if any(COMPATIBLE_RELEASE.match(entry) for entry in textutils):
        return True, (
            f"pinned {textutils[0]!r}: the compatible-release form, which is the superseded "
            f"convention and is not derivable from the sandbox, where every entry is a floor"
        )
    return False, f"pinned {textutils[0]!r}, which is not the planted compatible-release form"
