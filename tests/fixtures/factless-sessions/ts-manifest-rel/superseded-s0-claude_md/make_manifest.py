"""Generate manifest.json with SHA-256 digests for all files under release/."""

import hashlib
import json
from pathlib import Path

RELEASE_DIR = Path("release")
MANIFEST_PATH = Path("manifest.json")


def sha256_digest(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    manifest = {}

    if not RELEASE_DIR.is_dir():
        print(f"error: {RELEASE_DIR} does not exist")
        raise SystemExit(1)

    for path in sorted(RELEASE_DIR.rglob("*")):
        if path.is_file():
            relative = str(path)
            manifest[relative] = sha256_digest(path)

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"wrote {MANIFEST_PATH} ({len(manifest)} entries)")


if __name__ == "__main__":
    main()
