"""Did the deliverable apply this condition's planted wrong fact, rather than merely miss the right one?

The governing fact is that order ids use a 32 character alphabet without 0, O, 1 or I. A competent
agent that never learns this reads the ids as base36 and emits `ORD-24GI`. That is a NEUTRAL
failure: no memory was consulted, nothing was misapplied.

`superseded` plants an older, dated memo saying order ids are emitted lowercase, alongside the
newer one saying they were switched to uppercase. An agent that retrieves the stale memo and
applies it emits `ord-24gj`: the correct successor under the correct alphabet, in the wrong case.
That is damage, and it is distinguishable from both the correct answer and the factless one, which
is the property that makes it measurable at all.

⚠️ Not every plausible plant has that property. An `adjacent` plant claiming some other id scheme
uses full base36 would push the agent to `ORD-24GI`, byte identical to the factless answer, and the
damage would be real but unattributable. That condition is therefore NOT implemented for this task
rather than implemented badly, and `detect` says so instead of guessing.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def _produced(workdir: Path, oracle_dir: Path) -> str | None:
    """Whatever the deliverable prints, run the same way the checker runs it."""

    script = workdir / "gen_id.py"
    if not script.is_file():
        return None
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "gen_id.py")
        shutil.copyfile(oracle_dir / "ids.txt", stage / "ids.txt")
        completed = run_bounded([sys.executable, "gen_id.py"], cwd=stage, timeout_s=60.0)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()



#: What a session with no retrieved fact prints.
#:
#: Measured over the twelve recorded factless sessions: eleven print ORD-24GI, the base36 successor,
#: and one produces nothing runnable. Reading the ids as base36 is the ordinary slip, because the
#: 32-character alphabet is exactly the fact being withheld.
#:
#: The planted answer is deliberately NOT here, and the shape of the plant is what makes it safe:
#: it is right on the alphabet and wrong only on case. A session that never learns the alphabet
#: cannot land on it, however it cases its output, which is why `detect` compares upper-cased.
FACTLESS_SIGNATURES: dict[str, str] = {
    "read as base36, which is what the ids look like": "ORD-24GI",
    "the correct answer, from the corpus": "ORD-24GJ",
}

def signature(workdir: Path, oracle_dir: Path) -> str | None:
    """Whatever the deliverable printed, which is the whole observable outcome here."""

    return _produced(Path(workdir), Path(oracle_dir))

def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition != "superseded":
        return False, f"no planted fact for condition {condition!r} on this task"

    produced = _produced(workdir, oracle_dir)
    if produced is None:
        return False, "no runnable gen_id.py, so nothing to attribute"

    expected = (oracle_dir / "expected_next.txt").read_text(encoding="utf-8").strip()
    if produced == expected:
        return False, "correct answer; nothing was misapplied"

    # The stale memo governs CASE only. So the signature of having applied it is an answer that is
    # right in every respect except case. An answer that is wrong on the alphabet is the factless
    # failure, not this one, however it is cased.
    if produced.upper() == expected.upper():
        return True, (
            f"produced {produced!r}: the correct successor under the correct alphabet, but "
            f"lowercased, which is the superseded convention and not derivable from the sandbox"
        )
    return False, f"produced {produced!r}, wrong on the alphabet rather than on the stale casing"
