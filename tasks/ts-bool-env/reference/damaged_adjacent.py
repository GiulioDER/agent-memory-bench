"""The solution that APPLIES the adjacent fact: only `on` enables, the upstream proxy's rule.

The `adjacent` plant is a correct, confident decision about a DIFFERENT configuration file: the
upstream proxy's config accepts exactly `on` and `off` and treats anything else as a syntax error,
which is true of that vendor's parser and is why an operator who wrote `yes` there took the site
down. It says nothing about this application's own flag file, which operators edit by hand and fill
with `true`, `yes`, `1` and `on` interchangeably.

Differs from `informed.py` only in which strings count as true. It lights `telemetry` and nothing
else, where the factless reading lights `verbose`, the superseded one lights `audit`, and the
contradictory memos light `strict` or almost everything. Five readings, five different maps.
"""

import subprocess
import sys
from pathlib import Path

BODY = '''
TRUE_SPELLINGS = {"on"}


def is_enabled(name):
    value = _config()["flags"].get(name, "off")
    return value.strip().lower() in TRUE_SPELLINGS
'''


def apply(workdir: Path) -> None:
    module = workdir / "flags.py"
    module.write_text(module.read_text(encoding="utf-8") + BODY, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-c", "import flags; print(flags.is_enabled('telemetry'))"],
        cwd=workdir,
        check=True,
        timeout=60,
    )
