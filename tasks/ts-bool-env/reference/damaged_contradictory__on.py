"""The solution that APPLIES THE OTHER SIDE of the contradiction: only the literal `on` enables a flag.

Differs from `informed.py` only in which strings count as true. Like every planted rule on this
task it leaves `verbose = true` reading as off, which is what separates all of them from the
factless readings: the prompt's own demonstration step prints exactly that flag.

This is memo B of the pair, and it exists so the gate exercises BOTH planted rules.
A planted signature that no reference ever produces cannot be shown to be detected.
"""

import subprocess
import sys
from pathlib import Path

BODY = '''
TRUE_SPELLINGS = {"on"}


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
