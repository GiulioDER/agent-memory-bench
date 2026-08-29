#!/usr/bin/env python3
"""Generate manifest.json with SHA-256 digests for all files under release/."""

import hashlib
import json
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    release_dir = repo_root / "release"

    manifest = {}
    for path in sorted(release_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(release_dir).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest[rel_path] = digest

    (repo_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()