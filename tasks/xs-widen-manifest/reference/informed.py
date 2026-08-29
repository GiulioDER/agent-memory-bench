"""Both halves: the nightly manifest format, applied to a partner artifact."""

from pathlib import Path

SCRIPT = '''\
import hashlib
from pathlib import Path


def main():
    dist = Path("dist")
    entries = []
    for path in sorted(p for p in dist.rglob("*") if p.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        entries.append((path.relative_to(dist).as_posix(), digest))
    entries.sort()
    lines = [f"SHA256:{digest}  {rel}" for rel, digest in entries]
    lines.append(f"entries {len(entries)}")
    Path("manifest.txt").write_text("\\n".join(lines) + "\\n", encoding="utf-8")


if __name__ == "__main__":
    main()
'''


def apply(workdir: Path) -> None:
    (workdir / "make_manifest.py").write_text(SCRIPT, encoding="utf-8")
