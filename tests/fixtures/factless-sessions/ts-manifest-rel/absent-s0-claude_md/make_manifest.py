#!/usr/bin/env python3
"""Generate manifest.json with SHA-256 digests for all files under release/."""

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
RELEASE_DIR = REPO_ROOT / "release"
MANIFEST_PATH = REPO_ROOT / "manifest.json"


def sha256_digest(path: Path) -> str:
    """Return the hex SHA-256 digest of the file at *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    manifest = {}
    # Walk release/ in sorted order for deterministic output.
    for path in sorted(RELEASE_DIR.rglob("*")):
        if path.is_file():
            # Store the path relative to the repository root.
            rel = str(path.relative_to(REPO_ROOT))
            manifest[rel] = sha256_digest(path)

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"manifest.json written with {len(manifest)} entries.")


if __name__ == "__main__":
    main()
