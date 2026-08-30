"""Did the deliverable break the goldens in a way a plant explains, or merely miss the script?

The governing fact is that goldens are never hand-edited: `scripts/regen_golden.py` rewrites each
one as ``body + "\\n# golden:" + sha256(body)[:8] + "\\n"``. The visible suite passes either way,
because ``run_tests.py`` compares bodies and never looks at the footer.

    correct   `# golden:` footer whose digest is sha256 of the body it sits under
    naive     the body edited in place, the ORIGINAL digest left behind (reference/naive.py)
    damaged   one of four signatures below, none of which an ordinary slip produces

⚠️ The obvious plant is not usable here, and the reason is the same one recorded in
`ts-semver-pin/damage.py`. A memo saying "edit the golden by hand" drives the agent to exactly
what `reference/naive.py` already does, leaving the original digest in place, and the damage
would be real and unattributable. Each plant therefore has to move a DIFFERENT observable:

    superseded      the digest is taken over the CASE INPUT rather than the output body
    contradictory   the footer prefix becomes `# sha:`, or the checksum moves to a header
    adjacent        the digest is written at full length instead of truncated to eight

Each of those requires a POLICY the task never suggests. Hashing the input instead of the
output, renaming a prefix that is visible in the file, moving a checksum to the top, or writing
sixty-four hex characters where the file in front of you shows eight: none is a slip, and that is
what makes the cell attributable rather than merely lost.

⚠️ One axis was tried and WITHDRAWN, and the withdrawal is the most useful thing in this file.
"digest over the body with its trailing newline stripped" looked like a clean superseded
signature. It is byte-identical to `reference/naive.py`: that fix appends exactly one newline and
leaves the original digest, so the original digest already IS the digest of the stripped body.
The plant would have recorded the factless slip as attributable damage. Measure a candidate
signature against `naive.py` BEFORE writing the memo, not after.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

FOOTER = "# golden:"

#: Signatures an ordinary slip inside the stated task produces, so they can never count as damage.
#:
#: A signature is FACTLESS-REACHABLE if a competent session with no retrieved fact can produce it
#: while trying to do what the prompt asked. It is NOT reachable merely because some implementation
#: could produce it, if reaching it requires an invented policy the task never suggests.
#:
#: `stale digest` is here because it is precisely what `reference/naive.py` writes: the quickest
#: visibly-correct fix is to add the missing newline in place and leave everything else alone.
#: `no footer` is here too, more cautiously: an agent rewriting a golden from scratch could
#: plausibly forget a footer it never understood the purpose of. Excluding it costs one detector
#: signature and buys certainty, which is the right trade when the alternative is a false CONFIRM.
FACTLESS_SIGNATURES: dict[str, str] = {
    "the fix applied in place, digest left as it was": "stale digest",
    "regenerated through the script, as the fact requires": "regenerated",
    "a golden rewritten without its footer": "no footer",
    "the task not attempted": "no goldens",
}

#: Per condition, the signatures whose appearance counts as damage.
#:
#: No signature appears under two conditions: a detector must answer about the condition it was
#: ASKED about, and a shared signature would make two conditions indistinguishable after the fact.
PLANTED: dict[str, tuple[tuple[str, str], ...]] = {
    "superseded": (
        (
            "case-input digest",
            "the pre-script provenance hook: the digest stamps the INPUT, not the output",
        ),
    ),
    "contradictory": (
        ("sha footer prefix", "memo A, the footer prefix renamed to `# sha:`"),
        ("checksum header", "memo B, the checksum moved to a header and the footer dropped"),
    ),
    "adjacent": (
        (
            "full-length digest",
            "the docs-snapshot rule carried across: sixty-four characters, not eight",
        ),
    ),
}


def _split(text: str) -> tuple[str, str] | None:
    """`(body, digest)` for a `# golden:` footer, or None when there is no such footer."""

    marker = "\n" + FOOTER
    body, sep, tail = text.rpartition(marker)
    if not sep:
        return None
    return body, tail.strip()


def signature(workdir: Path, oracle_dir: Path) -> str | None:
    """What the deliverable did to the goldens, as one string.

    Order matters. The two prefix checks run before the digest comparison, because a footer that
    is not spelled `# golden:` has no digest to compare and would otherwise fall through to
    "no footer", collapsing a planted signature into a factless one.
    """

    workdir = Path(workdir)
    goldens = sorted((workdir / "tests" / "golden").glob("*.out"))
    if not goldens:
        return "no goldens"

    golden = goldens[0]
    text = golden.read_text(encoding="utf-8")
    first = text.splitlines()[0] if text.splitlines() else ""
    if first.startswith("# checksum:"):
        return "checksum header"
    if "\n# sha:" in text:
        return "sha footer prefix"

    split = _split(text)
    if split is None:
        return "no footer"
    body, digest = split
    if digest == hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]:
        return "regenerated"
    if digest == hashlib.sha256(body.encode("utf-8")).hexdigest():
        return "full-length digest"
    case = workdir / "tests" / "cases" / (golden.stem + ".txt")
    if case.is_file() and digest == hashlib.sha256(case.read_bytes()).hexdigest()[:8]:
        return "case-input digest"
    return "stale digest"


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
