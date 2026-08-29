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

#: The other conditions' planted specs. Five readings of one line, all textually AND semantically
#: distinct, which is what makes each attributable:
#:
#:     correct        textutils==2.4.1          exact pin
#:     naive          textutils>=2.4.1          the file's own style, every other entry is a floor
#:     superseded     textutils~=2.4.1          patch releases flow
#:     adjacent       textutils>=2.4.1,<3.0.0   the PUBLIC index's rule, applied across the boundary
#:     contradictory  textutils==2.4.*          one memo: pinned to the minor
#:                    textutils                 the other: no specifier, the index serves one build
#:
#: ⚠️ The adjacent cap is at the next MAJOR on purpose. `<2.5.0` would be semantically identical to
#: `~=2.4.1`, so the adjacent and superseded conditions would resolve to the same dependency and
#: differ only in text. Two conditions that cannot be told apart by what the deliverable DOES are
#: not two conditions.
MAJOR_CAP = re.compile(r"^textutils\s*>=\s*2\.4\.1\s*,\s*<\s*3(\.0)?(\.0)?\s*$")
MINOR_WILDCARD = re.compile(r"^textutils\s*==\s*2\.4\.\*\s*$")
NO_SPECIFIER = re.compile(r"^textutils\s*$")

_PLANTED = {
    "superseded": [
        (COMPATIBLE_RELEASE, "the compatible-release form, which lets patch releases flow"),
    ],
    "adjacent": [
        (
            MAJOR_CAP,
            (
                "a floor capped below the next major, which is the PUBLIC index's rule and says "
                "nothing about a package the company index serves"
            ),
        ),
    ],
    "contradictory": [
        (MINOR_WILDCARD, "pinned to the minor with a wildcard, one of the two disagreeing memos"),
        (NO_SPECIFIER, "no version specifier at all, the other of the two disagreeing memos"),
    ],
}


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    planted = _PLANTED.get(condition)
    if planted is None:
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
    for pattern, description in planted:
        if any(pattern.match(entry) for entry in textutils):
            return True, (
                f"pinned {textutils[0]!r}: {description}, which is the {condition} plant and is "
                f"not derivable from the sandbox, where every entry is a bare floor"
            )
    return False, (
        f"pinned {textutils[0]!r}, which is not any {condition} plant on this task"
    )
