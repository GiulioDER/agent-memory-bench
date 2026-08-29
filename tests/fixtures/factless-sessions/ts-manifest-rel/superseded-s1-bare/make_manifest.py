import hashlib
import json
import os


def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def build_manifest(release_dir: str = "release") -> dict[str, str]:
    """Build a dict mapping each file path under release_dir to its SHA-256 digest.

    Paths are relative to the repository root (i.e. prefixed with release_dir).
    """
    manifest: dict[str, str] = {}
    for root, dirs, files in os.walk(release_dir):
        # Sort for deterministic output
        dirs.sort()
        files.sort()
        for filename in files:
            abspath = os.path.join(root, filename)
            relpath = os.path.relpath(abspath, start=".")
            manifest[relpath] = compute_sha256(abspath)
    return manifest


def main() -> None:
    manifest = build_manifest()
    with open("manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
