#!/usr/bin/env python3
"""Copy project/ to backups/project/, creating backups/ if needed."""

import shutil
from pathlib import Path

src = Path(__file__).resolve().parent / "project"
dst = Path(__file__).resolve().parent / "backups" / "project"

dst.parent.mkdir(exist_ok=True)

# Remove existing backup if present so copytree works
if dst.exists():
    shutil.rmtree(dst)

shutil.copytree(src, dst, dirs_exist_ok=True)
