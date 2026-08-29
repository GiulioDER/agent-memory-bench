"""The solution that retrieved the SUPERSEDED fact and applied it.

It gets the alphabet right, which the sandbox alone cannot reveal, so it demonstrably consulted
memory. It then emits lowercase, which the newer memo says was changed to uppercase. The result is
the correct successor in the wrong case: wrong for a reason that only retrieval can produce.

This reference exists so the damage detector can be watched firing on a known-damaged sandbox, the
same way `informed.py` and `naive.py` let the checker be watched passing and failing. A detector
nobody has watched fire has not been tested.
"""

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
# The superseded memo: "order ids are emitted lowercase".
print(("ORD-" + encoded.rjust(4, ALPHABET[0])).lower())
'''


def apply(workdir: Path) -> None:
    (workdir / "gen_id.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "gen_id.py"], cwd=workdir, check=True, timeout=60)
