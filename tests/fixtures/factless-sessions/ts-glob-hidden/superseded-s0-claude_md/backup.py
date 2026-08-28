#!/usr/bin/env python3
"""Copy the project/ directory to backups/project/, preserving layout and contents."""

import shutil
from pathlib import Path

repo_root = Path(__file__).resolve().parent
src = repo_root / "project"
dst = repo_root / "backups" / "project"

# Remove destination if it already exists to avoid errors with copytree
if dst.exists():
    shutil.rmtree(dst)

# Create parent directory and copy
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(src, dst, symlinks=True)

print(f"Copied '{src}' to '{dst}'")
