"""The solution WITH the fact: sort key is casefolded and accent-stripped."""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import unicodedata


def sort_key(name):
    decomposed = unicodedata.normalize("NFD", name)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.casefold()


names = []
with open("attendees.txt", encoding="utf-8") as handle:
    for line in handle:
        if line.strip():
            names.append(line.strip())
with open("roster.txt", "w", encoding="utf-8") as out:
    for name in sorted(names, key=sort_key):
        out.write(name + "\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "roster.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "roster.py"], cwd=workdir, check=True, timeout=60)
