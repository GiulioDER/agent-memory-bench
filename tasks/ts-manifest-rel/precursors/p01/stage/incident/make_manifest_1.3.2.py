"""Manifest generator as run for the 1.3.2 release. Kept for the failed-verification investigation."""

import hashlib
import json
import os

manifest = {}
for dirpath, dirnames, filenames in os.walk(os.path.abspath("release")):
    for name in sorted(filenames):
        path = os.path.join(dirpath, name)
        with open(path, "rb") as handle:
            manifest[path] = hashlib.sha256(handle.read()).hexdigest()
with open("manifest.json", "w", encoding="utf-8") as out:
    json.dump(manifest, out, indent=2)
