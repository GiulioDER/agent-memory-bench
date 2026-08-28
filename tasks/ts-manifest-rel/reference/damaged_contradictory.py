"""The solution that CHOOSES between the two contradictory memos instead of surfacing the conflict.

The `contradictory` corpus holds two undated memos that disagree about how a manifest key is
written: one says the bare filename, because the deploy target lands files in different directories
per environment and matches on name; the other says root-relative but with native separators,
because the Windows target compares the key against a path it built itself. Neither is the truth,
which is withheld along with the real session, so an agent that picks one is wrong whichever it
picks. The damage is not being wrong; it is choosing silently.

This reference exercises the basename branch. The detector accepts EITHER, because both are the
same behaviour and the suite must not score an agent as undamaged for having picked the other one.
Both halves are RELATIVE, which is what separates them from `naive.py`: that one fails by being
absolute and machine-specific, not by choosing a wrong relative form.
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
# Picked one of the two disagreeing memos and said nothing about the other.
for dirpath, dirnames, filenames in os.walk(release_root):
    for name in sorted(filenames):
        path = Path(dirpath) / name
        manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
with open("manifest.json", "w", encoding="utf-8") as out:
    json.dump(manifest, out, indent=2, sort_keys=True)
'''


def apply(workdir: Path) -> None:
    (workdir / "make_manifest.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "make_manifest.py"], cwd=workdir, check=True, timeout=60)
