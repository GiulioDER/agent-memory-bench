#!/usr/bin/env python3
"""Generate manifest.json with SHA-256 digests for all files under release/."""

import hashlib
import json
import os

RELEASE_DIR = "release"
MANIFEST_PATH = "manifest.json"


def sha256_hex(filepath: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    manifest: dict[str, str] = {}

    for root, dirs, files in os.walk(RELEASE_DIR):
        # Sort for deterministic order
        dirs.sort()
        files.sort()
        for name in files:
            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, start=os.curdir)
            manifest[rel_path] = sha256_hex(full_path)

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Wrote {MANIFEST_PATH} with {len(manifest)} entries.")


if __name__ == "__main__":
    main()
