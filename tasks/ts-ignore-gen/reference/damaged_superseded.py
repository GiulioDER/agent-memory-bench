"""The solution that APPLIES the superseded fact: recent additions sit at the top.

Hand-edits the file like `naive.py` does, but inserts directly under the header instead of
appending. Every prior rule keeps its order, so the two failures differ only in where the new
line lands, which is the whole point: position is the signature of the planted rule.
"""

from pathlib import Path


def apply(workdir: Path) -> None:
    ignore_file = workdir / ".gitignore"
    lines = ignore_file.read_text(encoding="utf-8").splitlines()
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and line.strip().startswith("#"):
            out.append("dist2/")
            inserted = True
    if not inserted:
        out.insert(0, "dist2/")
    ignore_file.write_text("\n".join(out) + "\n", encoding="utf-8")
