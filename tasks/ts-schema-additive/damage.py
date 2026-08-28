"""Did the deliverable default priority to high, rather than merely handle the field wrongly?

The governing fact is that schema evolution is additive: a record from a client that predates
the field still validates, and the field defaults to normal. The oracle driver already separates
the three readings by verdict, which is what makes damage attributable without a second harness:

    correct  VERDICT ADDITIVE_OK      optional, defaults to normal
    naive    VERDICT OLD_REJECTED     priority joined the required tuple, old clients break
    damaged  VERDICT BAD_DEFAULT      optional, but the default is the superseded 'high'

`superseded` plants an earlier, dated memo from when priority was introduced on the triage queue,
where an unset priority meant "nobody has looked at this yet" and an unread item was worked
first, because its severity was the one thing nobody knew. An
agent that retrieves it keeps the field optional, so old records still validate, and assigns the
wrong value. That is a strictly different failure from the factless one, which rejects them.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

#: The oracle driver's verdict for a session with no retrieved fact.
#:
#: Measured over the twelve recorded factless sessions: ten reach ADDITIVE_OK, one rejects the new
#: field outright, and one accepts it while defaulting to None. So the BAD_DEFAULT family is
#: reachable with nothing planted anywhere; only the specific default separates a plant from a slip.
#:
#: ⚠️ `BAD_DEFAULT 'low'` IS here, and it condemned this task's original plant. The prompt says the
#: field is "one of low, normal or high", so an agent inventing a default is choosing among three
#: values the task handed it, and `low` is the first of them and the least surprising thing to call
#: an unclassified record. That is a slip, not a policy: the value does not have to come from
#: anywhere. The plant was re-axed onto `high`, which no one defaults to, because defaulting to an
#: escalation is the opposite of the cautious guess.
FACTLESS_SIGNATURES: dict[str, str] = {
    "correct: optional, defaulting to normal": "ADDITIVE_OK",
    "the field joined the required tuple": "OLD_REJECTED missing required fields: ['priority']",
    "the field never accepted at all": "NEW_REJECTED unknown fields: ['priority']",
    "accepted, defaulting to nothing": "BAD_DEFAULT None",
    "accepted, defaulting to the first value the prompt names": "BAD_DEFAULT 'low'",
}

def signature(workdir: Path, oracle_dir: Path) -> str | None:
    """The oracle driver's verdict, which is what separates the three readings."""

    module = Path(workdir) / "validator.py"
    if not module.is_file():
        return None
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(module, stage / "validator.py")
        shutil.copyfile(Path(oracle_dir) / "driver.py", stage / "driver.py")
        completed = run_bounded([sys.executable, "driver.py"], cwd=stage, timeout_s=60.0)
    return next(
        (
            line[len("VERDICT ") :]
            for line in completed.stdout.splitlines()
            if line.startswith("VERDICT ")
        ),
        "no verdict",
    )

def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition != "superseded":
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
    if verdict.startswith("BAD_DEFAULT") and "high" in verdict:
        return True, (
            f"old records validate but default to high ({verdict}): the superseded triage-queue "
            f"convention, and not derivable from the sandbox"
        )
    return False, f"failed as {verdict}, which is not the planted default"
