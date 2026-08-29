#!/usr/bin/env python3
"""Generate manifest.json with SHA-256 digests for all files under release/."""

import hashlib
import json
import os

RELEASE_DIR = "release"
MANIFEST_FILE = "manifest.json"


def sha256_digest(filepath: str) -> str:
    """Compute the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    manifest = {}

    for root, dirs, files in os.walk(RELEASE_DIR):
        for fn in sorted(files):
            full_path = os.path.join(root, fn)
            rel_path = os.path.relpath(full_path, start=os.getcwd())
            manifest[rel_path] = sha256_digest(full_path)

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"Written {MANIFEST_FILE} with {len(manifest)} entries.")


if __name__ == "__main__":
    main()
