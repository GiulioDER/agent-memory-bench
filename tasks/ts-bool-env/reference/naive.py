"""The competent solution WITHOUT the fact: compare against the two spellings the config uses.

Not careless. It lowercases, it strips, and it is exactly right for every value in the sandbox
config. It reads `off`, `no` and `0` as enabled, because nothing in the sandbox says an operator
ever writes those.
"""

import subprocess
import sys
from pathlib import Path

BODY = '''

def is_enabled(name):
    value = _config()["flags"].get(name, "false")
    return value.strip().lower() == "true"
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
