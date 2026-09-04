"""Retrieved p01 only: the nightly manifest format, believed to govern the nightly export alone.

This one is worth reading twice, because its behaviour is identical to `naive.py` and that is
the point rather than an oversight. p01 states a format and scopes it to the nightly export;
`dist/` is a release bundle. An agent that stops there has every reason to keep the June
release format, so a format retrieved without its widening changes nothing that ships. It must
fail, and it fails in exactly the same place a session with no memory at all fails.
"""

from pathlib import Path

SCRIPT = '''\
import hashlib
from pathlib import Path


def main():
    dist = Path("dist")
    lines = []
    for path in sorted(dist.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{path.relative_to(dist).as_posix()}: {digest}")
    Path("manifest.txt").write_text("\\n".join(lines) + "\\n", encoding="utf-8")


if __name__ == "__main__":
    main()
'''


def apply(workdir: Path) -> None:
    (workdir / "make_manifest.py").write_text(SCRIPT, encoding="utf-8")
