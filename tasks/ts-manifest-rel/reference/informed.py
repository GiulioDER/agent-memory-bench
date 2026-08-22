"""The solution WITH the fact: keys relative to the repo root, forward-slashed."""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import hashlib
import json
import os
from pathlib import Path

manifest = {}
repo_root = Path.cwd()
for dirpath, dirnames, filenames in os.walk(repo_root / "release"):
    for name in sorted(filenames):
        path = Path(dirpath) / name
        key = path.relative_to(repo_root).as_posix()
        manifest[key] = hashlib.sha256(path.read_bytes()).hexdigest()
with open("manifest.json", "w", encoding="utf-8") as out:
    json.dump(manifest, out, indent=2, sort_keys=True)
'''


def apply(workdir: Path) -> None:
    (workdir / "make_manifest.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "make_manifest.py"], cwd=workdir, check=True, timeout=60)
