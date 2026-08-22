"""The competent solution WITHOUT the fact: counts raw text, so a composed accent and its
decomposed twin stay two different words that render identically."""

from pathlib import Path

SCRIPT = '''\
from pathlib import Path

counts = {}
for doc in sorted(Path("docs").glob("*.txt")):
    for token in doc.read_text(encoding="utf-8").lower().split():
        token = token.strip(".,;:!?")
        if token:
            counts[token] = counts.get(token, 0) + 1
with open("counts.txt", "w", encoding="utf-8") as out:
    for word in sorted(counts):
        out.write(f"{word} {counts[word]}\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "count_words.py").write_text(SCRIPT, encoding="utf-8")
    import subprocess
    import sys

    subprocess.run([sys.executable, "count_words.py"], cwd=workdir, check=True, timeout=60)
