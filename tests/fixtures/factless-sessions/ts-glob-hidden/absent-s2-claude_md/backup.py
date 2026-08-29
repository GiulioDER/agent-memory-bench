#!/usr/bin/env python3
"""Backup the project/ directory to backups/project/."""

import shutil
from pathlib import Path

def main():
    src = Path("project")
    dst = Path("backups") / "project"

    # Create backups/ directory if needed
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing backup if present, then copy
    if dst.exists():
        shutil.rmtree(dst)

    shutil.copytree(src, dst)
    print(f"Backed up {src} to {dst}")

if __name__ == "__main__":
    main()