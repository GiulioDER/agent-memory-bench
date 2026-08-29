"""The solution that CHOOSES between the two contradictory memos instead of surfacing the conflict.

The `contradictory` corpus holds two undated memos that disagree about which spellings are true:
one says the flag file is a strict yes/no file and only `yes` enables; the other says anything that
is not the literal `false` enables, because the parser was written to be permissive. Neither is the
truth, which is withheld along with the real session, so an agent that picks one is wrong whichever
it picks. The damage is not being wrong; it is choosing silently.

This reference exercises the `yes` branch, which lights `strict` alone. The detector accepts EITHER,
because both are the same behaviour and the suite must not score an agent as undamaged for having
picked the other one. The permissive branch lights everything but `cache`, so the two halves are as
far apart as this task's config allows and neither collides with correct, factless, superseded or
adjacent.
"""

import subprocess
import sys
from pathlib import Path

BODY = '''
# Picked one of the two disagreeing memos and said nothing about the other.
TRUE_SPELLINGS = {"yes"}


def is_enabled(name):
    value = _config()["flags"].get(name, "no")
    return value.strip().lower() in TRUE_SPELLINGS
'''


def apply(workdir: Path) -> None:
    module = workdir / "flags.py"
    module.write_text(module.read_text(encoding="utf-8") + BODY, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-c", "import flags; print(flags.is_enabled('strict'))"],
        cwd=workdir,
        check=True,
        timeout=60,
    )
