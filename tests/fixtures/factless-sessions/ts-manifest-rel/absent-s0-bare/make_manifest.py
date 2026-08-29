#!/usr/bin/env python3
"""Generate manifest.json with SHA-256 digests for all files under release/."""

import hashlib
import json
from pathlib import Path

RELEASE_DIR = Path("release")
MANIFEST_PATH = Path("manifest.json")


def file_digest(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> None:
    manifest = {}

    if not RELEASE_DIR.is_dir():
        raise SystemExit(f"error: {RELEASE_DIR} does not exist")

    for entry in sorted(RELEASE_DIR.rglob("*")):
        if entry.is_file():
            relative = entry.as_posix()
            manifest[relative] = file_digest(entry)

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {MANIFEST_PATH} ({len(manifest)} entries)")


if __name__ == "__main__":
    main()
