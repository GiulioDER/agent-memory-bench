#!/usr/bin/env python3
"""Backup the project/ directory to backups/project/."""

import shutil
from pathlib import Path


def main() -> None:
    source = Path("project")
    dest = Path("backups") / "project"

    # Remove existing backup to get a clean copy
    if dest.exists():
        shutil.rmtree(dest)

    # Copy the entire directory tree
    shutil.copytree(source, dest)

    print(f"Copied {source}/ to {dest}/")


if __name__ == "__main__":
    main()
