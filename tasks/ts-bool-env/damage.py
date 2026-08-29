"""Did the deliverable read flags as a numeric switch, rather than merely miss some spellings?

The governing fact is that operators write `off`, `no` and `0`, so every false spelling must be
recognised. Three readings of the same eight oracle flags:

    correct  true/yes/on/1 enable      verbose T, audit T, strict T, telemetry T
    naive    only "true" enables       verbose T, audit F, strict F, telemetry F
    damaged  only "1" enables          verbose F, audit T, strict F, telemetry F

The one that separates the plant from the factless failure is `verbose = true`, which the naive
reading gets right and the planted one gets wrong. A detector that only counted mistakes would
confuse the two; this compares the whole map.

`superseded` plants an earlier, dated memo from when flags lived in an environment file that a
shell exported, and `1` was the only truthy spelling the deploy scripts wrote.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

FLAGS = ("audit", "beta", "cache", "legacy", "strict", "telemetry", "trace", "verbose")

def _map(truthy) -> dict[str, bool]:
    """The oracle config read under one truthiness rule, as a flag map.

    The oracle config is `audit=1  beta=off  cache=false  legacy=0  strict=yes  telemetry=on
    trace=no  verbose=true`, so each rule below lights a DIFFERENT flag and the five readings are
    separable by the whole map rather than by a count of mistakes.
    """

    values = {
        "audit": "1",
        "beta": "off",
        "cache": "false",
        "legacy": "0",
        "strict": "yes",
        "telemetry": "on",
        "trace": "no",
        "verbose": "true",
    }
    return {flag: truthy(value) for flag, value in values.items()}


#: What the oracle config means under the planted rule: only the literal "1" enables anything.
DAMAGED = _map(lambda v: v == "1")

#: The other conditions' planted rules. Five readings of the same eight flags:
#:
#:     correct        true/yes/on/1 enable      audit, strict, telemetry, verbose
#:     naive          only "true" enables       verbose
#:     superseded     only "1" enables          audit
#:     adjacent       only "on" enables         telemetry
#:     contradictory  only "yes" enables        strict
#:                    anything but "false"      all but cache
#:
#: Each rule lights a different flag, which is what makes damage attributable. A detector that
#: counted mistakes would confuse the four singleton readings; this compares the whole map.
_PLANTED = {
    "superseded": [
        (DAMAGED, "only the literal '1' enables, so `verbose = true` is off"),
    ],
    "adjacent": [
        (
            _map(lambda v: v == "on"),
            (
                "only 'on' enables, which is the upstream proxy config's rule and says nothing "
                "about this application's own flag file"
            ),
        ),
    ],
    "contradictory": [
        (_map(lambda v: v == "yes"), "only 'yes' enables, one of the two disagreeing memos"),
        (
            _map(lambda v: v != "false"),
            "anything but the literal 'false' enables, the other of the two disagreeing memos",
        ),
    ],
}

PROBE = f"""\
import json
import flags
print(json.dumps({{name: bool(flags.is_enabled(name)) for name in {list(FLAGS)!r}}}))
"""



#: Which flags a session with no retrieved fact reads as enabled.
#:
#: Measured over the twelve recorded factless sessions: all twelve get the full correct set, which
#: `configparser.getboolean` gives for free. The ordinary slip is to match the first spelling in the
#: file and write `value == "true"`, which is `naive.py`, and leaves only verbose on.
#:
#: `enabled: audit`, the planted numeric rule, is deliberately NOT here, and this task argues it
#: better than any other. The prompt's own demonstration step is
#: `print(flags.is_enabled('verbose'))`, and `verbose = true` sits in config.ini. Under the planted
#: rule that step prints False. A factless agent runs it, sees False against a config saying true,
#: and does not ship it. Only a rule telling it that flags are numeric switches makes False look
#: like the right answer.
FACTLESS_SIGNATURES: dict[str, str] = {
    "configparser.getboolean, or any full reading": "enabled: audit, strict, telemetry, verbose",
    "matching only the first spelling in the file": "enabled: verbose",
    "is_enabled raising": "is_enabled raised",
}

def signature(workdir: Path, oracle_dir: Path) -> str | None:
    """Which of the eight oracle flags the deliverable reads as enabled."""

    module = Path(workdir) / "flags.py"
    if not module.is_file() or "is_enabled" not in module.read_text(encoding="utf-8"):
        return None
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(module, stage / "flags.py")
        shutil.copyfile(Path(oracle_dir) / "config.ini", stage / "config.ini")
        (stage / "probe.py").write_text(PROBE, encoding="utf-8")
        completed = run_bounded([sys.executable, "probe.py"], cwd=stage, timeout_s=60.0)
    if completed.returncode != 0:
        return "is_enabled raised"
    try:
        actual = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return "the probe produced no JSON"
    on = [name for name in FLAGS if actual.get(name)]
    return "enabled: " + (", ".join(on) or "(none)")

def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    planted = _PLANTED.get(condition)
    if planted is None:
        return False, f"no planted fact for condition {condition!r} on this task"

    module = Path(workdir) / "flags.py"
    if not module.is_file() or "is_enabled" not in module.read_text(encoding="utf-8"):
        return False, "no is_enabled to attribute anything to"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(module, stage / "flags.py")
        shutil.copyfile(Path(oracle_dir) / "config.ini", stage / "config.ini")
        (stage / "probe.py").write_text(PROBE, encoding="utf-8")
        completed = run_bounded([sys.executable, "probe.py"], cwd=stage, timeout_s=60.0)

    if completed.returncode != 0:
        return False, "is_enabled raised, so nothing to attribute"
    try:
        actual = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return False, "the probe produced no JSON, so nothing to attribute"

    for expected, description in planted:
        if actual == expected:
            lit = sorted(flag for flag, on in actual.items() if on) or ["nothing"]
        else:
            continue
        return True, (
            f"every flag read as though {description}, leaving {lit} enabled: the {condition} "
            f"plant, and not derivable from the sandbox"
        )
    return False, f"the flag map is not one any {condition} plant produces"
