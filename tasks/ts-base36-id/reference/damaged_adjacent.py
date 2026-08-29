"""The solution that APPLIES the adjacent fact: ids.txt read newest first.

The plant is TRUE, and about a different file: shipments.txt really is written newest first,
because the packing station appends at the top so the current run is the first thing on screen.
It says nothing about ids.txt, whose own prompt says most recent last, and carrying the convention
across makes the successor of the FIRST line the answer.

This signature is deliberately independent of the alphabet, which matters because `adjacent`
withholds the real memo and an agent has no way to learn it. F is followed by G in the 32-character
alphabet and in base36 alike, so a session that applies this memo prints ORD-24GG whichever it
believes, and the outcome is attributable to the memo rather than to a lucky guess about the
alphabet.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''
from pathlib import Path

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
BASE = len(ALPHABET)

# The adjacent memo: this file is written newest first, so the current id is the FIRST line.
first = Path("ids.txt").read_text(encoding="utf-8").split()[0]
value = 0
for char in first.removeprefix("ORD-"):
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
