"""The shared-manifest convention applied: every key prefixed with the release version.

That was genuinely the rule while one manifest covered every release and keys had to stay
unique across them. Every digest is correct; only the key shape is wrong.

An earlier version of this fixture dropped the `release/` segment instead. That shape turned
out to be produced by real factless sessions, so it was withdrawn. See ../damage.py."""

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
            version = (root / "release" / "VERSION").read_text(encoding="utf-8").strip()
            manifest[version + "/" + rel] = digest
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
