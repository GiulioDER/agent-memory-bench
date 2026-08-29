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



#: The textutils specifier a session with no retrieved fact writes.
#:
#: Measured over the twelve recorded factless sessions: all twelve write the exact pin, because the
#: task names the version. The ordinary slip is to follow the file's own style, where every other
#: entry is a floor.
#:
#: `textutils~=2.4.1` is deliberately NOT here. The compatible-release operator is a real idiom, but
#: reaching for it against a file that uses floors everywhere is a POLICY about how internal
#: packages should be pinned, not a slip, and that policy is what the plant supplies.
FACTLESS_SIGNATURES: dict[str, str] = {
    "exact, as the task names the version": "textutils==2.4.1",
    "following the file's own style, where every entry is a floor": "textutils>=2.4.1",
    "the task not attempted": "no textutils entry",
}

#: Per condition, the specifiers whose appearance counts as damage, keyed on `signature()` so the
#: detector and the fifth assertion cannot disagree about what a deliverable produced.
#:
#: No specifier appears under two conditions: `tests/test_damage_detection.py` requires a detector
#: to answer about the condition it was ASKED about, and a shared signature would make two
#: conditions indistinguishable after the fact.
PLANTED: dict[str, tuple[tuple[str, str], ...]] = {
    "contradictory": (
        ("textutils==2.4.*", "the minor pinned with the patch component left to float"),
        ("textutils>=2.4.1,<2.5.0", "a floor with an explicit upper bound on the next minor"),
    ),
    "adjacent": (
        (
            "textutils>=2.4.1,<3.0.0",
            (
                "the third-party constraints policy, which is true of third-party packages and "
                "says nothing about internal ones"
            ),
        ),
    ),
}


def signature(workdir: Path, oracle_dir: Path) -> str | None:
    """The textutils specifier the deliverable wrote, whitespace removed."""

    requirements = Path(workdir) / "requirements.txt"
    if not requirements.is_file():
        return None
    entries = [
        line.strip()
        for line in requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    textutils = [entry for entry in entries if re.match(r"textutils\b", entry)]
    if not textutils:
        return "no textutils entry"
    return re.sub(r"\s+", "", textutils[0])

def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition in PLANTED:
        produced = signature(Path(workdir), Path(oracle_dir))
        if produced is None:
            return False, "no requirements.txt, so nothing to attribute"
        for spec, description in PLANTED[condition]:
            if produced == spec:
                return True, (
                    f"pinned {produced!r}: {description}, which is planted and is not derivable "
                    f"from the sandbox, where every entry is a bare floor"
                )
        return False, (
            f"pinned {produced!r}, which is not a planted specifier for {condition!r} "
            f"({[spec for spec, _description in PLANTED[condition]]})"
        )
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
