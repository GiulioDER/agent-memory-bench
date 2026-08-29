"""Generate manifest.json mapping release/ files to their SHA-256 digests."""

import hashlib
import json
import os

RELEASE_DIR = "release"
MANIFEST_FILE = "manifest.json"


def main() -> None:
    manifest = {}

    for root, dirs, files in os.walk(RELEASE_DIR):
        for filename in sorted(files):
            filepath = os.path.join(root, filename)
            # Compute SHA-256 digest
            sha256 = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            digest = sha256.hexdigest()
            manifest[filepath] = digest

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()