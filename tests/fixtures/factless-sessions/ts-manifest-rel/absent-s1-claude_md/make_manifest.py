#!/usr/bin/env python3
"""Generate manifest.json with SHA-256 digests for all files under release/."""

import hashlib
import json
import os

RELEASE_DIR = "release"
MANIFEST_FILE = "manifest.json"


def sha256_digest(filepath: str) -> str:
    """Return the hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    manifest: dict[str, str] = {}

    for root, _dirs, files in os.walk(RELEASE_DIR):
        for name in files:
            path = os.path.join(root, name)
            # Use forward slashes for cross-platform consistency
            key = os.path.relpath(path, RELEASE_DIR).replace(os.sep, "/")
            manifest[key] = sha256_digest(path)

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Written {MANIFEST_FILE} with {len(manifest)} entries.")


if __name__ == "__main__":
    main()