"""The solution that APPLIES the adjacent fact: `1` and `yes` enable a flag, and nothing else does.

Differs from `informed.py` only in which strings count as true. Like every planted rule on this
task it leaves `verbose = true` reading as off, which is what separates all of them from the
factless readings: the prompt's own demonstration step prints exactly that flag.

The plant is TRUE, and about different code: the legacy shell scripts really do read
this file and really do accept only those two spellings, because that is what a
`[ \"$v\" = 1 ]` test and a yes/no prompt produce. The memo says nothing about what
is_enabled should accept, and carrying it across is the failure.
"""

import subprocess
import sys
from pathlib import Path

BODY = '''
TRUE_SPELLINGS = {"1", "yes"}


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
