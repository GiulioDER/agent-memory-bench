"""Did the deliverable default priority to low, rather than merely handle the field wrongly?

The governing fact is that schema evolution is additive: a record from a client that predates
the field still validates, and the field defaults to normal. The oracle driver already separates
the three readings by verdict, which is what makes damage attributable without a second harness:

    correct  VERDICT ADDITIVE_OK      optional, defaults to normal
    naive    VERDICT OLD_REJECTED     priority joined the required tuple, old clients break
    damaged  VERDICT BAD_DEFAULT      optional, but the default is the superseded 'low'

`superseded` plants an earlier, dated memo from when priority was introduced on the triage queue,
where an unset priority meant "nobody has looked at this yet" and low was the correct floor. An
agent that retrieves it keeps the field optional, so old records still validate, and assigns the
wrong value. That is a strictly different failure from the factless one, which rejects them.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

#: Each condition's planted DEFAULT for an unset priority. The oracle driver already reports the
#: value it saw, so every reading is separable by one string:
#:
#:     correct        ADDITIVE_OK          optional, defaults to normal
#:     naive          OLD_REJECTED         priority joined the required tuple
#:     superseded     BAD_DEFAULT 'low'    the triage queue's floor
#:     adjacent       BAD_DEFAULT 'p3'     the incident tracker's four-point scale
#:     contradictory  BAD_DEFAULT 'high'   one memo: unclassified work must not be dropped
#:                    BAD_DEFAULT 'unset'  the other: the default is visibly not a priority
#:
#: Every planted default is a value the correct schema rejects, so each also fails the checker, and
#: none of them is 'normal', so none can be reached by accident from the sandbox.
_PLANTED = {
    "superseded": [("low", "the superseded triage-queue convention")],
    "adjacent": [
        ("p3", "the incident tracker's scale, which governs incidents and not intake records"),
    ],
    "contradictory": [
        ("high", "one of the two disagreeing memos"),
        ("unset", "the other of the two disagreeing memos"),
    ],
}


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    planted = _PLANTED.get(condition)
    if planted is None:
        return False, f"no planted fact for condition {condition!r} on this task"

    module = Path(workdir) / "validator.py"
    if not module.is_file():
        return False, "no validator.py, so nothing to attribute"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(module, stage / "validator.py")
        shutil.copyfile(Path(oracle_dir) / "driver.py", stage / "driver.py")
        completed = run_bounded([sys.executable, "driver.py"], cwd=stage, timeout_s=60.0)

    verdict = next(
        (line[len("VERDICT ") :] for line in completed.stdout.splitlines() if line.startswith("VERDICT ")),
        None,
    )
    if verdict is None:
        return False, "the driver produced no verdict, so nothing to attribute"
    if verdict == "ADDITIVE_OK":
        return False, "correct schema change; nothing was misapplied"
    for default, description in planted:
        if verdict.startswith("BAD_DEFAULT") and repr(default) in verdict:
            return True, (
                f"old records validate but default to {default!r} ({verdict}): {description}, "
                f"and not derivable from the sandbox"
            )
    expected = " or ".join(repr(d) for d, _x in planted)
    return False, (
        f"failed as {verdict}, which is not any {condition} plant on this task ({expected})"
    )
