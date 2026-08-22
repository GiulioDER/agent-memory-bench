"""The solution WITH the fact: positional ids over the 32-char alphabet without 0/O/1/I."""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
from pathlib import Path

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
BASE = len(ALPHABET)

last = Path("ids.txt").read_text(encoding="utf-8").split()[-1]
value = 0
for char in last.removeprefix("ORD-"):
    value = value * BASE + ALPHABET.index(char)
value += 1
encoded = ""
while value:
    value, remainder = divmod(value, BASE)
    encoded = ALPHABET[remainder] + encoded
print("ORD-" + encoded.rjust(4, ALPHABET[0]))
'''


def apply(workdir: Path) -> None:
    (workdir / "gen_id.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "gen_id.py"], cwd=workdir, check=True, timeout=60)
