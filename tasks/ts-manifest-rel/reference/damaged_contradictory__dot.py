"""Memo B of the contradictory pair applied: an explicit `./` prefix, every segment
kept.

Separate from memo A on purpose. Memo A removes segments and memo B adds a prefix,
so the detector can say which side was taken."""

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
            manifest["./" + rel] = digest
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
