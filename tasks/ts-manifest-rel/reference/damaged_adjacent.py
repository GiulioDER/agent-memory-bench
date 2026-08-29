"""The solution that APPLIES the adjacent fact: a leading slash, the CDN asset manifest's rule.

The `adjacent` plant is a correct, confident decision about a DIFFERENT manifest: the CDN asset
manifest keys every entry with a leading slash, because the keys are request paths and the edge
matches them against the URL it was asked for. True of that manifest, and it says nothing about the
one the deploy target reads to verify what it received.

Identical to `informed.py` apart from the prefix. The keys are root-relative and POSIX, so this is
not the superseded bundle-relative form and not the absolute backslashed form `naive.py` produces;
it is the right path addressed to the wrong reader.
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
repo_root = Path.cwd()
release_root = repo_root / "release"
for dirpath, dirnames, filenames in os.walk(release_root):
    for name in sorted(filenames):
        path = Path(dirpath) / name
        key = "/" + path.relative_to(repo_root).as_posix()
        manifest[key] = hashlib.sha256(path.read_bytes()).hexdigest()
with open("manifest.json", "w", encoding="utf-8") as out:
    json.dump(manifest, out, indent=2, sort_keys=True)
'''


def apply(workdir: Path) -> None:
    (workdir / "make_manifest.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "make_manifest.py"], cwd=workdir, check=True, timeout=60)
