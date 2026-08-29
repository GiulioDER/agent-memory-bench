"""Backup the project/ directory to backups/project/."""

import shutil
from pathlib import Path


def main():
    src = Path("project")
    dst = Path("backups") / "project"

    # Remove existing backup if present so copytree works cleanly
    if dst.exists():
        shutil.rmtree(dst)

    # Copy the entire directory tree
    shutil.copytree(src, dst)

    print(f"Copied {src}/ to {dst}/")


if __name__ == "__main__":
    main()
