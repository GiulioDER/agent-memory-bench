#!/usr/bin/env python3
"""Backup the project/ directory to backups/project/."""

import shutil
import sys
from pathlib import Path


def main() -> None:
    src = Path("project")
    dst = Path("backups") / "project"

    if not src.is_dir():
        print(f"Error: source directory '{src}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Remove existing backup so copytree works cleanly
    if dst.exists():
        shutil.rmtree(dst)

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    print(f"Backed up '{src}' -> '{dst}'")


if __name__ == "__main__":
    main()
