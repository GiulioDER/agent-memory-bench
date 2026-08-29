"""The solution that APPLIES the superseded fact: only the literal 1 enables a flag.

Differs from `informed.py` only in which strings count as true. It is not the naive reading:
that one accepts `true` and rejects `1`, this one does the opposite, so `verbose = true` is the
flag that tells them apart.
"""

import subprocess
import sys
from pathlib import Path

BODY = '''
TRUE_SPELLINGS = {"1"}


def is_enabled(name):
    value = _config()["flags"].get(name, "0")
    return value.strip().lower() in TRUE_SPELLINGS
'''


def apply(workdir: Path) -> None:
    module = workdir / "flags.py"
    module.write_text(module.read_text(encoding="utf-8") + BODY, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-c", "import flags; print(flags.is_enabled('verbose'))"],
        cwd=workdir,
        check=True,
        timeout=60,
    )
