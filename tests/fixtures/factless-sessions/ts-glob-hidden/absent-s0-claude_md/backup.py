#!/usr/bin/env python3
"""Copy project/ to backups/project/, creating backups/ if needed."""

import shutil
import sys
from pathlib import Path

SRC = Path("project")
DST = Path("backups") / "project"


def main():
    if not SRC.is_dir():
        print(f"Error: source directory '{SRC}' does not exist", file=sys.stderr)
        return 1

    if DST.exists():
        shutil.rmtree(DST)

    shutil.copytree(SRC, DST)
    print(f"Copied '{SRC}/' to '{DST}/'")
    return 0


if __name__ == "__main__":
    sys.exit(main())