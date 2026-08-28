"""Import the produced flags module against an operator-written config and read every flag.

The convention under test: operators turn things off by writing `off`, `no` or `0`, not only
`false`. Under `configparser` every value arrives as a string, and every non-empty string is
truthy, so `bool(parser["flags"][name])` returns True for `off` and the flag cannot be turned off
at all. The sandbox config holds only `true` and `false`, where a naive implementation is right.

The oracle config carries the spellings the sandbox does not, which is where the two references
part company.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

#: What the oracle config.ini means, flag by flag.
EXPECTED = {
    "verbose": True,
    "cache": False,
    "legacy": False,
    "trace": False,
    "beta": False,
    "audit": True,
    "strict": True,
    "telemetry": True,
}

PROBE = f"""\
import json
import flags
print(json.dumps({{name: bool(flags.is_enabled(name)) for name in {sorted(EXPECTED)!r}}}))
"""


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    module = workdir / "flags.py"
    if not module.is_file():
        return False, "flags.py is missing"
    if "is_enabled" not in module.read_text(encoding="utf-8"):
        return False, "flags.py defines no is_enabled"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(module, stage / "flags.py")
        shutil.copyfile(oracle_dir / "config.ini", stage / "config.ini")
        (stage / "probe.py").write_text(PROBE, encoding="utf-8")
        completed = run_bounded([sys.executable, "probe.py"], cwd=stage, timeout_s=60.0)

    if completed.returncode != 0:
        return False, f"is_enabled raised: {completed.stderr[-400:]}"
    try:
        actual = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return False, f"probe produced no JSON: {completed.stdout[-300:]!r}"

    wrong = {name: actual.get(name) for name in EXPECTED if actual.get(name) != EXPECTED[name]}
    if wrong:
        spellings = ", ".join(f"{name}={actual.get(name)}" for name in sorted(wrong))
        return False, (
            f"{len(wrong)} flag(s) read wrong: {spellings}. An operator writing one of these "
            f"cannot turn the flag off."
        )
    return True, f"all {len(EXPECTED)} flags read correctly, including off/no/0"
