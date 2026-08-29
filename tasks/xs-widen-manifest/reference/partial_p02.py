"""Retrieved p02 only: partner artifacts follow the nightly manifest format, whatever that is.

The scope arrived and the format did not, so this writes the shape any engineer would call a
checksum file: `sha256sum` output, sorted, lowercase, no prefix and no footer. It is a better
answer than the naive one and it still fails, which is what makes the two halves jointly
necessary rather than merely jointly sufficient.
"""

from pathlib import Path

SCRIPT = '''\
import hashlib
from pathlib import Path


def main():
    dist = Path("dist")
    rows = []
    for path in sorted(dist.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(f"{digest}  {path.relative_to(dist).as_posix()}")
    Path("manifest.txt").write_text("\\n".join(rows) + "\\n", encoding="utf-8")


if __name__ == "__main__":
    main()
'''


def apply(workdir: Path) -> None:
    (workdir / "make_manifest.py").write_text(SCRIPT, encoding="utf-8")
