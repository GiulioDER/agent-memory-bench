"""The solution that APPLIES the superseded fact: keys relative to release/, not the repo root.

Identical to `informed.py` apart from the directory the key is made relative to. The result is
POSIX, portable and stripped of the `release/` prefix, so it is wrong in a way `naive.py` never
produces: that one fails by being absolute.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import hashlib
import json
import os
from pathlib import Path

manifest = {}
release_root = Path.cwd() / "release"
for dirpath, dirnames, filenames in os.walk(release_root):
    for name in sorted(filenames):
        path = Path(dirpath) / name
        key = path.relative_to(release_root).as_posix()
        manifest[key] = hashlib.sha256(path.read_bytes()).hexdigest()
with open("manifest.json", "w", encoding="utf-8") as out:
    json.dump(manifest, out, indent=2, sort_keys=True)
'''


def apply(workdir: Path) -> None:
    (workdir / "make_manifest.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "make_manifest.py"], cwd=workdir, check=True, timeout=60)
