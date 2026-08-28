#!/usr/bin/env python3
import json
import hashlib
import os


def sha256_digest(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    release_dir = os.path.join(root_dir, "release")
    manifest = {}

    for dirpath, dirnames, filenames in os.walk(release_dir):
        for filename in filenames:
            # Get the full path to the file
            full_path = os.path.join(dirpath, filename)
            # Get the relative path from root_dir (e.g., "release/app/main.py")
            rel_path = os.path.relpath(full_path, root_dir)
            manifest[rel_path] = sha256_digest(full_path)

    manifest_path = os.path.join(root_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Written {len(manifest)} entries to {manifest_path}")


if __name__ == "__main__":
    main()
