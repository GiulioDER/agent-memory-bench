"""Pre-release backup helper, as run on 2026-07-24. Kept for the restore investigation."""

import glob
import os
import shutil

os.makedirs(os.path.join("backups", "project"), exist_ok=True)
for entry in glob.glob(os.path.join("project", "*")):
    destination = os.path.join("backups", entry)
    if os.path.isdir(entry):
        shutil.copytree(entry, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(entry, destination)
print("backup complete")
