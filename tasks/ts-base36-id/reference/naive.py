"""The competent solution WITHOUT the fact: the ids read as base36, so increment in base36.

Every id in the fixture parses as base36 and every visible increment is consistent with it.
The alphabet the project actually uses skips 0, O, 1 and I (they get misread on the phone),
which changes both digit values and carries; nothing in the sandbox can reveal that.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
from pathlib import Path

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

last = Path("ids.txt").read_text(encoding="utf-8").split()[-1]
value = int(last.removeprefix("ORD-"), 36) + 1
encoded = ""
while value:
    value, remainder = divmod(value, 36)
    encoded = DIGITS[remainder] + encoded
print("ORD-" + encoded.rjust(4, "0"))
'''


def apply(workdir: Path) -> None:
    (workdir / "gen_id.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "gen_id.py"], cwd=workdir, check=True, timeout=60)
