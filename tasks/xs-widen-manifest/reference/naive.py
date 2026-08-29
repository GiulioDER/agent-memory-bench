"""The competent solution WITHOUT the governing fact: follow the precedent in the repository.

`archive/2026-06/manifest.txt` is the only manifest the fixture contains, so reproducing its
shape for the new bundle is the obvious move and it is what an agent with no memory does. It
fails silently: the file is well formed, the hashes are correct, and only the partner's verifier
knows the format changed in May.
"""

from pathlib import Path

SCRIPT = '''\
import hashlib
from pathlib import Path


def main():
    dist = Path("dist")
    lines = []
    for path in dist.rglob("*"):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{path.relative_to(dist).as_posix()}: {digest}")
    Path("manifest.txt").write_text("\\n".join(lines) + "\\n", encoding="utf-8")


if __name__ == "__main__":
    main()
'''


def apply(workdir: Path) -> None:
    (workdir / "make_manifest.py").write_text(SCRIPT, encoding="utf-8")
