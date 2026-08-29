#!/usr/bin/env python3
"""Generate manifest.json with SHA-256 digests for all files under release/."""

import hashlib
import json
import os

RELEASE_DIR = "release"
MANIFEST_PATH = "manifest.json"


def sha256_digest(filepath: str) -> str:
    """Return the SHA-256 hex digest of the given file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    manifest = {}
    root = os.path.abspath(os.path.dirname(__file__))
    release_root = os.path.join(root, RELEASE_DIR)

    for dirpath, _dirnames, filenames in os.walk(release_root):
        for filename in sorted(filenames):
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root)
            manifest[rel_path] = sha256_digest(full_path)

    manifest_path = os.path.join(root, MANIFEST_PATH)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Wrote {manifest_path} with {len(manifest)} entries.")


if __name__ == "__main__":
    main()
