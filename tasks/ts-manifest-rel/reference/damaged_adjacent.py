"""The vendor-index rule carried across: the mapping inverted, digests as keys and
paths as values.

The memo it comes from is TRUE and scopes itself to the vendor manifest, which really
is digest-keyed so an identical blob shipped at two paths appears once. A release
manifest has the opposite requirement, which that memo says in its own words."""

import hashlib
import json
import os
from pathlib import Path


def apply(workdir: Path) -> None:
    manifest = {}
    root = Path(workdir)
    for dirpath, _dirnames, filenames in os.walk(root / "release"):
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest[digest] = rel
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
