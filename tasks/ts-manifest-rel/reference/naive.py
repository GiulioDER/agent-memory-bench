"""The competent solution WITHOUT the fact: walk from an absolute root, keys as str(path).

os.walk over an absolute root yields absolute paths, and str() of a Windows path uses
backslashes. The manifest is well-formed JSON, every digest is right, and every key is
useless anywhere but this machine. Nothing in the sandbox reads the manifest back.
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
root = Path.cwd() / "release"
for dirpath, dirnames, filenames in os.walk(root):
    for name in sorted(filenames):
        path = Path(dirpath) / name
        manifest[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
with open("manifest.json", "w", encoding="utf-8") as out:
    json.dump(manifest, out, indent=2, sort_keys=True)
'''


def apply(workdir: Path) -> None:
    (workdir / "make_manifest.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "make_manifest.py"], cwd=workdir, check=True, timeout=60)
