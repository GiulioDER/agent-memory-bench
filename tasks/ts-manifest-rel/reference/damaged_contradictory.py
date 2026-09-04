"""Memo A of the contradictory pair applied: every directory segment dropped, leaving
the basename.

Supported by a real audit showing basenames are unique within a release, which is
what makes the memo persuasive rather than obviously wrong."""

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
            manifest[rel.rsplit('/', 1)[-1]] = digest
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
