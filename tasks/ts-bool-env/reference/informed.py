"""The solution WITH the fact: the full set of spellings an operator actually writes.

Differs from `naive.py` only in which strings count as true. Lookup, default and stripping are
unchanged.
"""

import subprocess
import sys
from pathlib import Path

BODY = '''
TRUE_SPELLINGS = {"true", "yes", "on", "1"}


def is_enabled(name):
    value = _config()["flags"].get(name, "false")
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
