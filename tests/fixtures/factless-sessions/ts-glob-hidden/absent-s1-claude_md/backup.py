#!/usr/bin/env python3
"""Backup project/ to backups/project/."""

import shutil
from pathlib import Path

src = Path("project")
dst = Path("backups") / "project"

dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(src, dst, dirs_exist_ok=True)

print(f"Copied {src}/ to {dst}/")